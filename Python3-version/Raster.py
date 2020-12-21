import gdal, osr
from os import path
import numpy as np
from logger import Logger
from scipy import interpolate
# this allows GDAL to throw Python Exceptions
gdal.UseExceptions()

class Raster:
    class PointShift:
        CENTER=(0.5, -0.5)
        TOPLEFT=(1.0, -1.0)
        TOPRIGHT=(1.0, 0)
        BOTTOMLEFT=(0.0, -1.0)
        BOTTOMRIGHT=(0.0, 1.0)

    def __init__(self, *args, **kwargs):
        self.log = Logger("Raster")
        self.filename = kwargs.get('filepath', None)

        # Got a file. Load it
        if self.filename is not None:
            self.errs = ""
            try:
                src_ds = gdal.Open( self.filename )
            except RuntimeError as e:
                self.log.error('Unable to open %s' % self.filename, e)
                raise e
            try:
                # Read Raster Properties
                srcband = src_ds.GetRasterBand(1)
                self.bands = src_ds.RasterCount
                self.driver = src_ds.GetDriver().LongName
                self.gt = src_ds.GetGeoTransform()
                self.nodata = srcband.GetNoDataValue()
                """ Turn a Raster with a single band into a 2D [x,y] = v array """
                self.array = srcband.ReadAsArray()

                # Now mask out any NAN or nodata values (we do both for consistency)
                if self.nodata is not None:
                    self.array = np.ma.array(self.array, mask=(np.isnan(self.array) | (self.array == self.nodata)))

                self.dataType = srcband.DataType
                self.min = np.nanmin(self.array)
                self.max = np.nanmax(self.array)

                if self.min is np.ma.masked:
                    self.min = np.nan
                if self.max is np.ma.masked:
                    self.max = np.nan

                self.proj = src_ds.GetProjection()

                # Remember:
                # [0]/* top left x */
                # [1]/* w-e pixel resolution */
                # [2]/* rotation, 0 if image is "north up" */
                # [3]/* top left y */
                # [4]/* rotation, 0 if image is "north up" */
                # [5]/* n-s pixel resolution */
                self.left = self.gt[0]
                self.cellWidth = self.gt[1]
                self.top = self.gt[3]
                self.cellHeight = self.gt[5]
                self.cols = src_ds.RasterXSize
                self.rows = src_ds.RasterYSize
                # Important to throw away the srcband
                srcband.FlushCache()
                srcband = None

            except RuntimeError as e:
                self.log.error('Could not retrieve meta Data for %s' % self.filepath, e)
                raise e

        # No file to load. this is a new raster
        else:
            self.nodata = kwargs.get('nodata', -9999.0)
            self.min = None
            self.max = None
            self.array = None

            self.rows = int(kwargs.get('rows', 0))
            self.cols = int(kwargs.get('cols', 0))
            self.cellWidth = float(kwargs.get('cellWidth', 0.1))
            self.cellHeight = float(kwargs.get('cellHeight', -self.cellWidth))
            self.proj = kwargs.get('proj', "")
            self.dataType = kwargs.get('dataType', gdal.GDT_Float32)

            tempArray = kwargs.get('array', None)
            if tempArray is not None:
                self.setArray(tempArray)
                self.min = np.nanmin(self.array)
                self.max = np.nanmax(self.array)

            extent = kwargs.get('extent', None)

            # Expecting extent in the form [Xmin, Xmax, Ymin, Ymax]
            if extent is not None:
                self.left = float(extent[0] if self.cellWidth > 0 else extent[1]) # What we mean by left is : top left 'X'
                self.top = float(extent[2] if self.cellHeight > 0 else extent[3])  # What we mean by top is : top left 'Y'

                self.rows = abs(int(round((extent[3] - extent[2]) / self.cellHeight)))
                self.cols = abs(int(round((extent[1] - extent[0]) / self.cellWidth)))
            else:
                self.top = float(kwargs.get('top', -9999.0))
                self.left = float(kwargs.get('left', -9999.0))

    def loadDEMFromCSV(self, sCSVPath, theExtent, ptCenter=None):
        """
        Populate a raster's grid with values from a CSV file
        :param sCSVPath:
        :return:
        """
        if not ptCenter:
            ptCenter = self.PointShift.CENTER
        fileArr = np.loadtxt(open(sCSVPath, "rb"), delimiter=" ")

        # Set up an empty array with the right size
        z_array = np.empty((self.rows, self.cols))
        z_array[:] = np.nan

        # If there is a :, python will pass .cellHeight))a slice:
        # Remember: theExtent = (Xmin, Xmax, Ymin, Ymax)
        X = (fileArr[:, 1] - (theExtent[0] + ( ptCenter[0]*self.cellWidth ))).astype(int)
        Y = (fileArr[:, 2] - (theExtent[2] + ( ptCenter[1]*self.cellHeight))).astype(int)

        # Assign every point in the flat array to a grid point
        z_array[Y, X] = fileArr[:, 3]

        # This array might be upside-down from GDAL's perspective
        if self.cellHeight < 0:
            self.setArray(np.flipud(z_array), True)
        else:
            self.setArray(z_array, True)

    def MetaCopy(self):
        """
        Copy everything but the array
        :return:
        """
        return Raster(left=self.left, top=self.top, nodata=self.nodata, proj=self.proj,
                           dataType=self.dataType, cellWidth=self.cellWidth, cellHeight=self.cellHeight)

    def MergeMinSurface(self, rDEM):
        """
        :param rDEM:
        :return:
        """
        # TODO: the masks are more complicated than this but we can make assumptions
        # because we always get to the mask the same way.
        minArr = np.ma.masked_invalid(np.fmin(self.array.data, rDEM.array.data))

        self.setArray(minArr)

    def ResampleDEM(self, newCellSize, method):
        """
        Resample the raster and return a new resampled raster
        current raster
        :param newCellSize:
        :param method:
        :return:
        """
        # Create a blank copy with everything but the array
        newDEM = self.MetaCopy()

        self.log.debug("Resampling original data from {0}m to {1}m using {2} method".format(self.cellWidth, newCellSize, method))
        arrayResampled = None

        XaxisOld, YaxisOld = np.ma.masked_array(np.mgrid[0:self.rows:self.cellWidth, 0:self.cols:abs(self.cellHeight)],
                                                (self.array.mask, self.array.mask))

        XaxisNew, YaxisNew = np.mgrid[0:self.rows:newCellSize, 0:self.cols:newCellSize]
        newMask = interpolate.griddata((XaxisOld.ravel(), YaxisOld.ravel()), self.array.mask.ravel(),
                                                  (XaxisNew, YaxisNew), method='nearest', fill_value=np.nan)

        # Put us in the middle of the cell
        XaxisOld += abs(self.cellWidth) / 2
        YaxisOld += abs(self.cellHeight) / 2

        # Bilinear is a lot slower that the others and it's its own
        # method, written based on the
        # well known wikipedia article.
        if method == "bilinear":
            # Now we resample based on the method passed in here.
            fFactor = self.cellWidth / newCellSize
            newShape = (int(self.rows * fFactor), int(self.cols * fFactor))
            arrayResampled = bilinearResample(self.array, newShape)
        elif method == "linear" or method == "cubic" or method == "nearest":
            arrayResampled = interpolate.griddata((XaxisOld.ravel(), YaxisOld.ravel()), self.array.ravel(),
                                                  (XaxisNew, YaxisNew), method=method, fill_value=np.nan)
        else:
            raise Exception("Resample Method: '{0}' not recognized".format(method))

        # Set the new cell size and set the new array
        newDEM.cellWidth = newCellSize
        newDEM.cellHeight = -newCellSize
        newDEM.setArray(np.ma.masked_array(arrayResampled, newMask), False)
        self.log.debug("Successfully Resampled Raster")
        return newDEM

    def setArray(self, incomingArray, copy=False):
        """
        You can use the self.array directly but if you want to copy from one array
        into a raster we suggest you do it this way
        :param incomingArray:
        :return:
        """
        masked = isinstance(self.array, np.ma.MaskedArray)
        if copy:
            if masked:
                self.array = np.ma.copy(incomingArray)
            else:
                self.array = np.ma.masked_invalid(incomingArray, copy=True)
        else:
            if masked:
                self.array = incomingArray
            else:
                self.array = np.ma.masked_invalid(incomingArray)

        self.rows = self.array.shape[0]
        self.cols = self.array.shape[1]
        self.min = np.nanmin(self.array)
        self.max = np.nanmax(self.array)

    def write(self, outputRaster):
        """
        Write this raster object to a file. The Raster is closed after this so keep that in mind
        You won't be able to access the raster data after you run this.
        :param outputRaster:
        :return:
        """
        if path.isfile(outputRaster):
            deleteRaster(outputRaster)

        driver = gdal.GetDriverByName('GTiff')
        outRaster = driver.Create(outputRaster, self.cols, self.rows, 1, self.dataType, ['COMPRESS=LZW'])

        # Remember:
        # [0]/* top left x */
        # [1]/* w-e pixel resolution */
        # [2]/* rotation, 0 if image is "north up" */
        # [3]/* top left y */
        # [4]/* rotation, 0 if image is "north up" */
        # [5]/* n-s pixel resolution */
        outRaster.SetGeoTransform([self.left, self.cellWidth, 0, self.top, 0, self.cellHeight])
        outband = outRaster.GetRasterBand(1)

        # Set nans to the original No Data Value
        outband.SetNoDataValue(self.nodata)
        self.array.data[np.isnan(self.array)] = self.nodata
        # Any mask that gets passed in here should have masked out elements set to
        # Nodata Value
        if isinstance(self.array, np.ma.MaskedArray):
            np.ma.set_fill_value(self.array, self.nodata)
            outband.WriteArray(self.array.filled())
        else:
            outband.WriteArray(self.array)

        spatialRef = osr.SpatialReference()
        spatialRef.ImportFromWkt(self.proj)

        outRaster.SetProjection(spatialRef.ExportToWkt())
        outband.FlushCache()
        # Important to throw away the srcband
        outband = None
        self.log.debug("Finished Writing Raster: {0}".format(outputRaster))

    def PrintRawArray(self):
        """
        Raw print of raster array values. useful to visualize rasters on the command line
        :return:
        """
        print("\n----------- Raw Array -----------")
        masked = isinstance(self.array, np.ma.MaskedArray)
        for row in range(self.array.shape[0]):
            rowStr = ' '.join(map(str, self.array[row])).replace('-- ', '- ').replace('nan ', '_ ')
            print("{0}:: {1}".format(row, rowStr))
        print("\n")

    def PrintArray(self):
        """
        Print the array flipped if the cellHeight is negative
        useful to visualize rasters on the command line
        :return:
        """
        arr = None
        strFlipped = "False"
        if self.cellHeight >= 0:
            arr = np.flipud(self.array)
            strFlipped = "True"
        else:
            arr = self.array
        print("\n----------- Array Flip: {0} -----------".format(strFlipped))
        masked = isinstance(arr, np.ma.MaskedArray)
        for row in range(arr.shape[0]):
            rowStr = ' '.join(map(str, arr[row])) + ' '
            rowStr = rowStr.replace('-- ', '- ').replace('nan ', '_ ')
            print("{0}:: {1}".format(row, rowStr))
        print("\n")

    def ASCIIPrint(self):
        """
        Print an ASCII representation of the array with an up-down flip if the
        the cell height is negative.

        Int this scenario:
            - '-' means masked
            - '_' means nodata
            - '#' means a number
            - '0' means 0
        :param arr:
        """
        arr = None
        if self.cellHeight >= 0:
            arr = np.flipud(self.array)
        else:
            arr = self.array
        print("\n")
        masked = isinstance(arr, np.ma.MaskedArray)
        for row in range(arr.shape[0]):
            rowStr = ""
            for col in range(arr[row].shape[0]):
                colStr = str(arr[row][col])
                if colStr == 'nan':
                    rowStr+= "_"
                elif masked and arr.mask[row][col]:
                    rowStr += "-"
                elif arr[row][col] == 0:
                    rowStr += "0"
                else:
                    rowStr += "#"
            print("{0}:: {1}".format(row, rowStr))
        print("\n")


def deleteRaster(sFullPath):
    """

    :param path:
    :return:
    """

    log = Logger("Delete Raster")

    if path.isfile(sFullPath):
        try:
            # Delete the raster properly
            driver = gdal.GetDriverByName('GTiff')
            gdal.Driver.Delete(driver, sFullPath)
            log.debug("Raster Successfully Deleted: {0}".format(sFullPath))
        except Exception as e:
            log.error("Failed to remove existing clipped raster at {0}".format(sFullPath))
            raise e
    else:
        log.debug("No raster file to delete at {0}".format(sFullPath))

def bilinearResample(oldGrid, newShape):
    '''
    :param oldGrid: A 2D array. This must be a regularly spaced grid (like a raster band array)
    :param newShape: the new shape you want in tuple format eg: (200,300)
    :return: newArr: The resampled array.
    '''
    newArr = np.nan * np.empty(newShape)
    oldCols, oldRows = oldGrid.shape
    newCols, newRows = newShape
    xMult = float(newCols) / oldCols # 4 in our test case
    yMult = float(newRows) / oldRows

    for (x, y), element in np.ndenumerate(newArr):
        # do a transform to figure out where we are ont he old matrix
        fx = x / xMult
        fy = y / yMult

        ix1 = int(np.floor(fx))
        iy1 = int(np.floor(fy))

        # Special case where point is on upper bounds
        if fx == float(newCols - 1):
            ix1 -= 1
        if fy == float(newRows - 1):
            iy1 -= 1

        ix2 = ix1 + 1
        iy2 = iy1 + 1

        # Test if we're within the raster midpoints
        if (ix1 >= 0) and (iy1 >= 0) and (ix2 < oldCols) and (iy2 < oldRows):
            # get the 4 values we need
            vals = [oldGrid[ix1,iy1], oldGrid[ix1,iy2], oldGrid[ix2,iy1], oldGrid[ix2,iy2]]

            # Here's where the actual interpolation is but make sure
            # there aren't any nan values.
            if not np.any([np.isnan(v) for v in vals]):
                newArr[x,y] = (vals[0] * (ix2 - fx) * (iy2 - fy) + vals[1] * (fx - ix1) * (iy2 - fy) + vals[2] * (ix2 - fx) * (fy - iy1) + vals[3] * (fx - ix1) * (fy - iy1)) / ((ix2 - ix1) * (iy2 - iy1) + 0.0)

    return newArr


def array2raster_template(array, outputRaster, templateRaster):
    """
    This is similar to the function above only it gets its initial values from an
    input "template" raster. Useful when creating a new raster based on an old one
    :param array:
    :param outputRaster:
    :param templateRaster:
    :return:
    """
    raster = Raster(filepath=templateRaster)
    raster.setArray(array)
    raster.write(outputRaster)




