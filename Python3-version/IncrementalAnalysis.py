from RasterAnalysis import getVolumeAndArea
from Raster import Raster
from logger import Logger
import csv

def RunIncrementalAnalysis(dSites, fElevationBenchmark, fElevationIncrement, fRasterCellSize, sResultFilePath):
    """

    :param dSites: Dictionary of all SandbarSite objects to be processed.
    :param fElevationBenchmark: The lower limit of the analysis (typically 8K discharge)
    :param fElevationIncrement: Vertical increment at which to perform the analysis (default is 0.1m)
    :param fRasterCellSize: The raster cell size (m)
    :return:
    """

    log = Logger("Inc. Analysis")
    log.info("Starting incremental analysis...")
    lModelResults = []

    for siteID, site in dSites.items():

        # Only process sites that have computation extent polygons
        if site.Ignore:
            continue

        log.info("Incremental analysis on site {0} with {1} surveys.".format(site.siteCode5, len(site.surveyDates)))

        for surveyID, surveyDate in site.surveyDates.items():

            # Only proceed with this survey if it is flagged to be apart of the analysis.
            if surveyDate.IsAnalysis:

                for sectionTypeID, section in surveyDate.surveyedSections.items():

                    # Only process sections that have computation extent polygons
                    if section.Ignore:
                        continue
                    log.debug("Incremental on site {0}, survey {1}, {2} {3}".format(
                        site.siteCode5,
                        surveyDate.SurveyDate.strftime('%Y-%m-%d'),
                        section.SectionType,
                        section.rasterPath))

                    # Run the analysis on this section and get back a list of tuples (Elevation, Area, Volume)
                    lSectionResults = RunSection(site, section, fElevationBenchmark, fElevationIncrement, fRasterCellSize)

                    if lSectionResults is None:
                        # Nothing found
                        log.info("No section results found.")
                    else:
                        # Append the results to the master list that will be written to the output CSV file
                        for (fElevation, fArea, fVolume) in lSectionResults:
                            lModelResults.append((site.siteID, site.siteCode5, surveyDate.SurveyID,
                                                         surveyDate.SurveyDate.strftime("%Y-%m-%d"),
                                                         section.SectionTypeID, section.SectionType,
                                                         section.SectionID, '{:.2f}'.format(fElevation), fArea, fVolume))


    log.info("Incremental analysis complete. Writing {0} results to {1}".format(len(lModelResults), sResultFilePath))

    with open(sResultFilePath, 'w') as out:
        csv_out = csv.writer(out)

        # Header row
        csv_out.writerow(['siteid', 'sitecode', 'surveyid', 'surveydate', 'sectiontypeid', 'section',
                          'sectionid', 'elevation', 'area', 'volume'])

        # Write the tuple of analysis results
        for row in lModelResults:
            csv_out.writerow(row)


def RunSection(site, section, fElevationBenchmark, fElevationIncrement, fRasterCellSize):

    # The results for this section will be a list of tuples (Elevation, Area, Volume)
    lSectionResults = []

    # Open the clipped raster for this site, survey and section and get the minimum surveyed elevation in this section
    rSurvey = Raster(filepath=section.rasterPath)
    analysisElevation = site.getMinAnalysisStage(rSurvey.min, fElevationBenchmark, fElevationIncrement)

    if analysisElevation is None:
        # There is no survey data in this section
        return None

    # We do the diff once and then mask it later
    assert rSurvey.array.size == site.MinimumSurface.array.size, "The two arrays are not the same size!"

    while analysisElevation < rSurvey.max:
        tAreaVol = (-1.0, -1)
        tAreaVol = getVolumeAndArea(rSurvey.array, site.MinimumSurface.array, analysisElevation, None,
                                    fRasterCellSize, site.MinimumSurfacePath)

        if tAreaVol[0] > 0:
            lSectionResults.append((analysisElevation, tAreaVol[0], tAreaVol[1]))

        analysisElevation += fElevationIncrement

    return lSectionResults
