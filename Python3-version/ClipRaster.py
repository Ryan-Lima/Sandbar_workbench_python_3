import os
from subprocess import call
import subprocess
from Raster import deleteRaster
from logger import Logger

def ClipRaster(gdalWarpPath, sInputRaster, sOutputRaster, sShapeFile, sWhereClause):
    log = Logger("Clip Raster")
    assert os.path.isfile(gdalWarpPath), "Missing GDAL Warp executable at {0}".format(gdalWarpPath)
    assert os.path.isfile(sInputRaster), "Missing clipping operation input at {0}".format(sInputRaster)
    assert os.path.isfile(sShapeFile.FullPath), "Missing clipping operation input ShapeFile at {0}".format(sShapeFile.FullPath)

    # Make sure the rasters get removed before they get re-made
    deleteRaster(sOutputRaster)

    # Reset the where parameter to an empty string if no where clause is provided
    # TODO: This is giving us 64-bit rasters for some reason and a weird nodata value with nan as well. We're probably losing precision somewhere
    sWhereParameter = ""
    if len(sWhereClause) > 0:
        sWhereParameter = "-cwhere \"{0}\"".format(sWhereClause)

    gdalArgs = " -cutline {0} {1} {2} {3}".format(sShapeFile.FullPath, sWhereParameter, sInputRaster, sOutputRaster)
    log.debug("RUNNING GdalWarp: " + gdalWarpPath + gdalArgs)

    theReturn = call(gdalWarpPath + gdalArgs, stdout=subprocess.PIPE, shell=True)
    assert theReturn == 0, "Error clipping raster. Input raster {0}. Output raster {1}. ShapeFile {2}".format(sInputRaster, sOutputRaster, sShapeFile.FullPath)
    