import os

class SandbarSurvey:

    def __init__(self, SurveyID, SurveyDate, txtPointsPath, isAnalysis, isMinSurface):
        self.SurveyID = SurveyID
        self.SurveyDate = SurveyDate
        self.txtPointsPath = txtPointsPath
        self.VRTFilePath = "" # populated by generateVRTFile method
        self.DEMPath = "" # populated by SandbarSite.GenerateDEMRasters
        self.IsAnalysis = isAnalysis # Whether this survey will be incorporated into the analysis
        self.IsMinSurface = isMinSurface # Whether this survey will be incorporated into the minimum surface

        # dictionary of section types that are part of this survey. Index is SectionTypeID
        self.surveyedSections = {}

    # Return the layer name for the txt Points file. This should
    # be the base file name of the txt file. Note that GDAL expects
    # this string as ASCII and not unicode.
    def getPointsLayerName(self):
        return os.path.splitext(os.path.basename(self.txtPointsPath))[0].encode("ascii", "ignore")

def getfile_insensitive(path):
    directory, filename = os.path.split(path)
    directory, filename = (directory or '.'), filename.lower()
    for f in os.listdir(directory):
        newpath = os.path.join(directory, f)
        if os.path.isfile(newpath) and f.lower() == filename:
            return newpath

def isfile_insensitive(path):
    return getfile_insensitive(path) is not None
