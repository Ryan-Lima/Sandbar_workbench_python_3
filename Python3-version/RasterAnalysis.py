import numpy as np
import copy
from Raster import array2raster_template

# Calculates the volume for a survey raster and minimum surface. If lower elevation is
# null then the calculation is up to the upper elevation. If the upper elevation is null
# then the analysis is above the lower elevation. If both are valid then the analysis is
# greater than or equal to the lower elevation and less than the upper elevation. i.e.
#
# Lower is null then analysis < upper
# Upper is null then analysis >= lower
# Both valid then analysis >= lower and < upper
#
def getVolumeAndArea(arSurvey, arMinimum, fLowerElevation, fUpperElevation, fCellSize, MinimumSurfacePath):

    if fLowerElevation is None:
        assert fUpperElevation is not None, "An upper elevation must be provided if the lower elevation is not provided."
    else:
        assert fLowerElevation >=0, "The lower elevation ({0}) must be greater than or equal to zero.".format(fLowerElevation)
        if fUpperElevation is not None:
            assert fLowerElevation < fUpperElevation, "The lower elevation ({0}) must be less than the upper elevation ({1}).".format(fLowerElevation, fUpperElevation)

    if fUpperElevation is not None:
        assert fUpperElevation >=0, "The upper elevation ({0}) must be greater than or equal to zero.".format(fUpperElevation)

    # Only proceed and calculate the area and volume if the survey is not entirely masked.
    # This shouldn't be needed, b the Workbench might have sections for surveys where no data were collected.
    if np.ma.MaskedArray.count(arSurvey) == 0:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    # We will create a new, custom minimum surface:
    arNewMinSrf = np.empty_like(arMinimum)
    # Quick Deep copy of arMinimum:
    arNewMinSrf[:] = arMinimum
    arNewMinSrf = np.ma.masked_where(arSurvey.mask, arNewMinSrf, True)

    template = {"area" : 0.0, "volume" : 0.0}
    surveyAboveUpper  = copy.copy(template)
    minSurfAboveUpper = copy.copy(template)

    fNewLowerElevation = fLowerElevation
    if fLowerElevation is None:
        fNewLowerElevation = np.min(arSurvey)

    surveyAboveLower = getAboveElev(arSurvey, fNewLowerElevation, fCellSize)
    minSurfAboveLower = getAboveElev(arNewMinSrf, fNewLowerElevation, fCellSize)

    if fUpperElevation:
        surveyAboveUpper = getAboveElev(arSurvey, fUpperElevation, fCellSize)
        minSurfAboveUpper = getAboveElev(arNewMinSrf, fUpperElevation, fCellSize)

    surveyNetVol = surveyAboveLower["volume"] - surveyAboveUpper["volume"]
    minSurfNetVol = minSurfAboveLower["volume"] - minSurfAboveUpper["volume"]
    netVolume = surveyNetVol - minSurfNetVol

    area = surveyAboveLower["area"] - surveyAboveUpper["area"]

    return (area, netVolume, surveyAboveLower["volume"], minSurfAboveLower["area"], minSurfAboveLower["volume"], minSurfNetVol)

def getAboveElev(arValues, fElevation, fCellSize):
    areaAboveElev =  np.ma.MaskedArray.count(arValues[arValues > fElevation]) * fCellSize**2
    volAboveElev = 0.0
    if areaAboveElev > 0:
        volAboveElev = np.nansum(arValues[arValues > fElevation]) * fCellSize**2 - (areaAboveElev * fElevation)
    return {"area" : areaAboveElev, "volume" : volAboveElev}