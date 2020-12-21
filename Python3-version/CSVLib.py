# Parse a delimited text file of volcano data and create a shapefile
from logger import Logger
import numpy as np


def unionCSVExtents(csvfiles, delimiter=" ", cellSize=1.0, padding=10.0):
    """
    Take a list of csvfiles and finds the unioned extent of them
    We are assuming csvfile points are the center of the cell so we
    also introduce a shift by 1/2 cell height and width so that
    the raster cell centers line up
    :param csvfiles:
    :param delimiter:
    :param cellSize:
    :param padding:
    :return:
    """
    cellSize = float(cellSize)
    log = Logger("unionCSVExtents")
    valueExtent = None

    for file in csvfiles:

        fileArr = np.loadtxt(open(file, "rb"), delimiter=delimiter)

        # Get the extents (plus some padding):
        XMax = np.amax(fileArr[:, 1])
        YMax = np.amax(fileArr[:, 2])

        XMin = np.amin(fileArr[:, 1])
        YMin = np.amin(fileArr[:, 2])

        fileExtent = (XMin, XMax, YMin, YMax)

        if not valueExtent:
            valueExtent = fileExtent[:] # Slice deep copy
        else:
            valueExtent = (min(fileExtent[0], valueExtent[0]),
                           max(fileExtent[1], valueExtent[1]),
                           min(fileExtent[2], valueExtent[2]),
                           max(fileExtent[3], valueExtent[3]) )

    log.debug("Uncorrected extent for {1} delimited files is {0}".format(valueExtent, len (csvfiles)))

    # We're calculating the extent of cell centers. To get the extent of
    # the raster we need to shift by one half cell.
    padAndShift = (padding * cellSize) + cellSize / 2

    # tuple(x + y for x, y in zip((0, -1, 7), (3, 4, -7)))
    correctedExtent = (
        valueExtent[0] - padAndShift,
        valueExtent[1] + padAndShift,
        valueExtent[2] - padAndShift,
        valueExtent[3] + padAndShift
    )
    log.debug("Corrected extent for {1} delimited files is {0}".format(correctedExtent, len(csvfiles)))

    return correctedExtent