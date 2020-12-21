from osgeo import ogr
import os
import osr
import gdal
from logger import Logger
SiteCode_Field = "Site"
Section_Field = "Section"

class ComputationExtents:

    def __init__(self, sFullPath, nEPSGID):
        self.FullPath = sFullPath
        self.log = Logger("Comp. Extents")

        Section_Eddy = "eddy"
        Section_Separation = "separation"
        Section_Reattachment = "reattachment"

        assert os.path.isfile(self.FullPath), "The computation extents ShapeFile does not exist at ".format(self.FullPath)

        try:
            driver = ogr.GetDriverByName('ESRI Shapefile')
            #driver = gdal.GetDriverByName('ESRI Shapefile')
            dataSource = driver.Open(self.FullPath, 0)


                                    # 0 means read-only. 1 means writeable.
        except RuntimeError as e:
            raise Exception("Unable to open computation extent ShapeFile {0}".format(self.FullPath))

        # Check to see if shapefile is found.
        assert dataSource is not None, "Could not open computation extents ShapeFile {1}".format(self.FullPath)

        # Make sure that there's at least one feature
        layer = dataSource.GetLayer()
        nFeatures = layer.GetFeatureCount()
        assert nFeatures > 0, "The computation extents ShapeFile is empty {0}".format(self.FullPath)

        # Check that the spatial reference matches the EPSGID
        source_srs = layer.GetSpatialRef()
        self.log.debug("Found SRS: {0}".format(source_srs.ExportToWkt()))

        desiredRef = osr.SpatialReference()
        if nEPSGID is int:
            desiredRef.ImportFromEPSG(nEPSGID)
        else:
            desiredRef.ImportFromWkt(nEPSGID)

        assert desiredRef.IsSame(source_srs), "The spatial reference of the computation extents ({0}) does not match that of the desired EPSG ID: {1}".format(source_srs, desiredRef)

        # Validate that the site code and section fields both exist
        bSiteField = False
        bSectionField = False
        layerDefinition = layer.GetLayerDefn()
        for i in range(layerDefinition.GetFieldCount()):
            if layerDefinition.GetFieldDefn(i).GetName() == SiteCode_Field:
                # fieldTypeCode = layerDefinition.GetFieldDefn(i).GetType()
                # fieldType = layerDefinition.GetFieldDefn(i).GetFieldTypeName(fieldTypeCode)
                # TODO: check field type is string
                bSiteField = True

            elif layerDefinition.GetFieldDefn(i).GetName() == Section_Field:
                # TODO: check field type is string
                bSectionField = True

        assert bSiteField, "Unable to find the site code field '{0}' in the computation extent ShapeFile.".format(SiteCode_Field)
        assert bSectionField, "Unable to find the site code field '{0}' in the computation extent ShapeFile.".format(Section_Field)

        self.log.info("Computational boundaries polygon ShapeFile loaded containing {0} features.".format(nFeatures))

    def getExtents(feature):
        """
        Return the extents of an OGR feature
        :param feature:
        :return:
        """
        geometry = feature.GetGeometryRef()
        return geometry.GetEnvelope()

    def extentUnion(oldExtents, newExtents):
        """
        Union two tuples representing a bounding triangle (x1, x2, y1, y2, n)
        n is the collected number of features in the extent (this is mostly for fun)
        :param oldExtents:
        :param newExtents:
        :return:
        """
        x1 = oldExtents[0] if oldExtents[0] < newExtents[0] else newExtents[0]
        x2 = oldExtents[1] if oldExtents[1] > newExtents[1] else newExtents[1]

        y1 = oldExtents[2] if oldExtents[2] < newExtents[2] else newExtents[2]
        y2 = oldExtents[3] if oldExtents[3] > newExtents[3] else newExtents[3]

        newN = oldExtents[4] + 1
        return (x1, x2, y1, y2, newN)

    def getFilterClause(self, siteCode, sectionType):

        sectionWhere = sectionType
        nHyphon = sectionWhere.find("-")
        if nHyphon >= 0:
            if "single" in sectionWhere[nHyphon:].lower():
                sectionWhere = sectionWhere[:nHyphon]
            else:
                sectionWhere = sectionWhere[nHyphon +1:]

        sectionWhere = sectionWhere.replace(" ", "")
        return "(\"{0}\" ='{1}')  AND (\"{2}\"='{3}')".format(SiteCode_Field, siteCode, Section_Field, sectionWhere)

    def ValidateSiteCodes(self, lSites):
        """
        Validates that at least one feature for each site can be found
        Pass in a list SandbarSite objects.
        :param lSites:
        :return:
        """
        driver = ogr.GetDriverByName('ESRI Shapefile')
        dataSource = driver.Open(self.FullPath, 0) # 0 means read-only. 1 means writeable.
        layer = dataSource.GetLayer()

        for SiteID, aSite in lSites.items():
            layer.SetAttributeFilter("{0} = '{1}'".format(SiteCode_Field, aSite.siteCode5))
            nFeatures = layer.GetFeatureCount()
            lMissingSections = {}

            if nFeatures >= 1:
                # Loop over all surveys and ensure that each section also occurs in the ShapeFile
                for SurveyID, aDate in aSite.surveyDates.items():
                    for sectionID, aSection in aDate.surveyedSections.items():

                        layer.SetAttributeFilter(self.getFilterClause(aSite.siteCode5, aSection.SectionType))
                        nFeatures = layer.GetFeatureCount()

                        if nFeatures < 1:
                            aSection.Ignore = True
                            lMissingSections[aSection.SectionType] = "missing"

                # Now report just once for any missing sections for this site
                for sectionType in lMissingSections:
                    self.log.warning(
                        "Site {0} missing polygon feature for section type '{1}'. This section will not be processed for any surveys at this site.".format(
                            aSite.siteCode5, sectionType))
            else:
                aSite.Ignore = True
                self.log.warning("Site {0} missing polygon feature(s) in computational extent ShapeFile. This site will not be processed.".format(aSite.siteCode5))

        self.log.info("Computation extents ShapeFile confirmed to contain at least one polygon for all {0} sandbar site(s) loaded.".format(len(lSites)))
