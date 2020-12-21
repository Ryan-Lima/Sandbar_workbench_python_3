from RasterAnalysis import getVolumeAndArea
from Raster import Raster
from logger import Logger
import csv

def RunBinnedAnalysis(dSites, dAnalysisBins, fRasterCellSize, sResultFilePath):

    lModelResults = []
    log = Logger("Binned Analysis")
    log.info("Starting binned analysis...")

    for siteID, site in dSites.items():

        # Only process sites that have computation extent polygons
        if site.Ignore:
            continue

        log.info("Binned analysis on site {0} with {1} surveys.".format(site.siteCode5, len(site.surveyDates)))

        # Loop over all the surveys for the site and perform the binned (<8k,
        # 8-25k, > 25k) analysis
        for surveyID, surveyDate in site.surveyDates.items():

            # Only proceed with this survey if it is flagged to be apart of the analysis.
            if surveyDate.IsAnalysis:

                for sectionTypeID, section in surveyDate.surveyedSections.items():

                    # Only process sections that have computation extent polygons
                    if section.Ignore:
                        continue

                    rSurvey = Raster(filepath=section.rasterPath)

                    for binID, bin in dAnalysisBins.items():

                            # Get the lower and upper elevations for the discharge.  Either
                            # could be None
                            fLowerElev = site.getStage(bin.lowerDischarge)
                            fUpperElev = site.getStage(bin.upperDischarge)

                            tAreaVol = getVolumeAndArea(rSurvey.array, site.MinimumSurface.array, fLowerElev, fUpperElev, fRasterCellSize, site.MinimumSurfacePath)

                            lModelResults.append((siteID, site.siteCode5, surveyID, surveyDate.SurveyDate.strftime("%Y-%m-%d"),
                                                 section.SectionTypeID, section.SectionType,
                                                 section.SectionID, binID, bin.title, tAreaVol[0], tAreaVol[1], tAreaVol[2], tAreaVol[3], tAreaVol[4], tAreaVol[5]))

    # Write the binned results to CSV
    log.info("Binned analysis complete. Writing {0} results to {1}".format(len(lModelResults), sResultFilePath))

    with open(sResultFilePath, 'w') as out:
        csv_out = csv.writer(out)
        csv_out.writerow(['siteid','sitecode','surveyid','surveydate','sectiontypeid','sectiontype','sectionid','binid','bin','area','volume','surveyvol','minsurfarea','minsurfvol','netminsurfvol'])
        for row in lModelResults:
            csv_out.writerow(row)
