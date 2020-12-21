import sqlite3
from logger import Logger

class SandbarSurveySection:

    def __init__(self, nSectionID, nSectionTypeID, sSectionType):
        self.SectionID = nSectionID
        self.SectionTypeID = nSectionTypeID
        self.SectionType = sSectionType
        self.rasterPath = ""
        self.Ignore = False

def LoadSandbarSurveySections(WorkbenchDB, lSites):
    """
    Load the SanbarSurveySections
    :param WorkbenchDB:
    :param lSites:
    :return:
    """
    log = Logger("LoadSurveySections")
    conn = sqlite3.connect(WorkbenchDB)

    try:
        c = conn.cursor()
        nSurveySections = 0

        # Load all sections for all surveys and all sites
        c.execute("SELECT S.SiteID, S.SiteCode5, SS.SurveyID, SSS.SectionTypeID, SSS.SectionID, L.Title FROM (((SandbarSites S INNER JOIN SandbarSurveys SS ON S.SiteID = SS.SiteID) INNER JOIN SandbarSections SSS ON SS.SurveyID = SSS.SurveyID) INNER JOIN LookupListItems L ON SSS.SectionTypeID = L.ItemID)")
        for aRow in c.fetchall():

            if aRow[0] in lSites:
                if aRow[2] in lSites[aRow[0]].surveyDates:
                    # The site and survey are loaded

                    assert not aRow[3] in lSites[aRow[0]].surveyDates[aRow[2]].surveyedSections, "The SurveyID {0} for site {1} ({2}) contains duplicate survey sections with SectionTypeID {3}".format(aRow[2], aRow[0], aRow[1], aRow[3])
                    lSites[aRow[0]].surveyDates[aRow[2]].surveyedSections[aRow[3]] = SandbarSurveySection(aRow[4], aRow[3], aRow[5])
                    nSurveySections += 1
    finally:
        conn.close()
        log.info("{0} sandbar survey sections loaded from the database.".format(nSurveySections))
