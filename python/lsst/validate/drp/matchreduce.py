# LSST Data Management System
# Copyright 2016 AURA/LSST.
#
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <https://www.lsstcorp.org/LegalNotices/>.
"""Blob classes that reduce a multi-visit dataset and encapsulate data
for measurement classes, plotting functions, and JSON persistence.
"""

from __future__ import print_function, absolute_import

import numpy as np
import astropy.units as u

import lsst.afw.geom as afwGeom
import lsst.afw.image as afwImage
import lsst.afw.image.utils as afwImageUtils
import lsst.daf.persistence as dafPersist
from lsst.afw.table import (SourceCatalog, SchemaMapper, Field,
                            MultiMatch, SimpleRecord, GroupView)
from lsst.afw.fits.fitsLib import FitsError
from lsst.validate.base import BlobBase

from .util import (getCcdKeyName, averageRaDecFromCat)


__all__ = ['MatchedMultiVisitDataset', 'positionRms']


class MatchedMultiVisitDataset(BlobBase):
    """Container for matched star catalogs from multple visits, with filtering,
    summary statistics, and modelling.

    `MatchedMultiVisitDataset` instances are serializable to JSON.

    Parameters
    ----------
    repo : `str`
        The repository.  This is generally the directory on disk
        that contains the repository and mapper.
    dataIds : `list` of `dict`
        List of `butler` data IDs of Image catalogs to compare to reference.
        The `calexp` cpixel image is needed for the photometric calibration.
    matchRadius :  afwGeom.Angle(), optional
        Radius for matching. Default is 1 arcsecond.
    safeSnr : `float`, optional
        Minimum median SNR for a match to be considered "safe".
    verbose : `bool`, optional
        Output additional information on the analysis steps.

    Attributes
    ----------
    filterName : `str`
        Name of filter used for all observations.
    mag : `astropy.units.Quantity`
        Mean PSF magnitudes of stars over multiple visits (magnitudes).
    magerr : `astropy.units.Quantity`
        Median 1-sigma uncertainty of PSF magnitudes over multiple visits
        (magnitudes).
    magrms : `astropy.units.Quantity`
        RMS of PSF magnitudes over multiple visits (magnitudes).
    snr : `astropy.units.Quantity`
        Median signal-to-noise ratio of PSF magnitudes over multiple visits
        (dimensionless).
    dist : `astropy.units.Quantity`
        RMS of sky coordinates of stars over multiple visits (milliarcseconds).
    goodMatches
        all good matches, as an afw.table.GroupView;
        good matches contain only objects whose detections all have

        1. a PSF Flux measurement with S/N > 1
        2. a finite (non-nan) PSF magnitude. This separate check is largely
           to reject failed zeropoints.
        3. and do not have flags set for bad, cosmic ray, edge or saturated

        *Not serialized.*

    safeMatches
        safe matches, as an afw.table.GroupView. Safe matches
        are good matches that are sufficiently bright and sufficiently
        compact.

        *Not serialized.*
    magKey
        Key for `"base_PsfFlux_mag"` in the `goodMatches` and `safeMatches`
        catalog tables.

        *Not serialized.*
    """

    name = 'MatchedMultiVisitDataset'

    def __init__(self, repo, dataIds, matchRadius=None, safeSnr=50.,
                 verbose=False):
        BlobBase.__init__(self)

        self.verbose = verbose
        if not matchRadius:
            matchRadius = afwGeom.Angle(1, afwGeom.arcseconds)

        # Extract single filter
        self.register_datum(
            'filterName',
            quantity=set([dId['filter'] for dId in dataIds]).pop(),
            description='Filter name')

        # Register datums stored by this blob; will be set later
        self.register_datum(
            'mag',
            label='{band}'.format(band=self.filterName),
            description='Mean PSF magnitudes of stars over multiple visits')
        self.register_datum(
            'magrms',
            label='RMS({band})'.format(band=self.filterName),
            description='RMS of PSF magnitudes over multiple visits')
        self.register_datum(
            'magerr',
            label='sigma({band})'.format(band=self.filterName),
            description='Median 1-sigma uncertainty of PSF magnitudes over '
                        'multiple visits')
        self.register_datum(
            'snr',
            label='SNR({band})'.format(band=self.filterName),
            description='Median signal-to-noise ratio of PSF magnitudes over '
                        'multiple visits')
        self.register_datum(
            'dist',
            label='d',
            description='RMS of sky coordinates of stars over multiple visits')

        # Match catalogs across visits
        self._matchedCatalog = self._loadAndMatchCatalogs(
            repo, dataIds, matchRadius)
        self.magKey = self._matchedCatalog.schema.find("base_PsfFlux_mag").key
        # Reduce catalogs into summary statistics.
        # These are the serialiable attributes of this class.
        self._reduceStars(self._matchedCatalog, safeSnr)

    def _loadAndMatchCatalogs(self, repo, dataIds, matchRadius):
        """Load data from specific visit. Match with reference.

        Parameters
        ----------
        repo : string
            The repository.  This is generally the directory on disk
            that contains the repository and mapper.
        dataIds : list of dict
            List of `butler` data IDs of Image catalogs to compare to
            reference. The `calexp` cpixel image is needed for the photometric
            calibration.
        matchRadius :  afwGeom.Angle(), optional
            Radius for matching. Default is 1 arcsecond.

        Returns
        -------
        afw.table.GroupView
            An object of matched catalog.
        """
        # Following
        # https://github.com/lsst/afw/blob/tickets/DM-3896/examples/repeatability.ipynb
        butler = dafPersist.Butler(repo)
        dataset = 'src'

        # 2016-02-08 MWV:
        # I feel like I could be doing something more efficient with
        # something along the lines of the following:
        #    dataRefs = [dafPersist.ButlerDataRef(butler, vId) for vId in dataIds]

        ccdKeyName = getCcdKeyName(dataIds[0])

        schema = butler.get(dataset + "_schema", immediate=True).schema
        mapper = SchemaMapper(schema)
        mapper.addMinimalSchema(schema)
        mapper.addOutputField(Field[float]('base_PsfFlux_snr',
                                           'PSF flux SNR'))
        mapper.addOutputField(Field[float]('base_PsfFlux_mag',
                                           'PSF magnitude'))
        mapper.addOutputField(Field[float]('base_PsfFlux_magerr',
                                           'PSF magnitude uncertainty'))
        newSchema = mapper.getOutputSchema()

        # Create an object that matches multiple catalogs with same schema
        mmatch = MultiMatch(newSchema,
                            dataIdFormat={'visit': int, ccdKeyName: int},
                            radius=matchRadius,
                            RecordClass=SimpleRecord)

        # create the new extented source catalog
        srcVis = SourceCatalog(newSchema)

        for vId in dataIds:
            try:
                calexpMetadata = butler.get("calexp_md", vId, immediate=True)
            except FitsError as fe:
                print(fe)
                print("Could not open calibrated image file for ", vId)
                print("Skipping %s " % repr(vId))
                continue
            except TypeError as te:
                # DECam images that haven't been properly reformatted
                # can trigger a TypeError because of a residual FITS header
                # LTV2 which is a float instead of the expected integer.
                # This generates an error of the form:
                #
                # lsst::pex::exceptions::TypeError: 'LTV2 has mismatched type'
                #
                # See, e.g., DM-2957 for details.
                print(te)
                print("Calibration image header information malformed.")
                print("Skipping %s " % repr(vId))
                continue

            calib = afwImage.Calib(calexpMetadata)

            oldSrc = butler.get('src', vId, immediate=True)
            print(len(oldSrc), "sources in ccd %s  visit %s" %
                  (vId[ccdKeyName], vId["visit"]))

            # create temporary catalog
            tmpCat = SourceCatalog(SourceCatalog(newSchema).table)
            tmpCat.extend(oldSrc, mapper=mapper)
            tmpCat['base_PsfFlux_snr'][:] = tmpCat['base_PsfFlux_flux'] \
                / tmpCat['base_PsfFlux_fluxSigma']
            with afwImageUtils.CalibNoThrow():
                _ = calib.getMagnitude(tmpCat['base_PsfFlux_flux'],
                                       tmpCat['base_PsfFlux_fluxSigma'])
                tmpCat['base_PsfFlux_mag'][:] = _[0]
                tmpCat['base_PsfFlux_magerr'][:] = _[1]

            srcVis.extend(tmpCat, False)
            mmatch.add(catalog=tmpCat, dataId=vId)

        # Complete the match, returning a catalog that includes
        # all matched sources with object IDs that can be used to group them.
        matchCat = mmatch.finish()

        # Create a mapping object that allows the matches to be manipulated
        # as a mapping of object ID to catalog of sources.
        allMatches = GroupView.build(matchCat)

        return allMatches

    def _reduceStars(self, allMatches, safeSnr=50.0):
        """Calculate summary statistics for each star. These are persisted
        as object attributes.

        Parameters
        ----------
        allMatches : afw.table.GroupView
            GroupView object with matches.
        safeSnr : float, optional
            Minimum median SNR for a match to be considered "safe".
        """
        # Filter down to matches with at least 2 sources and good flags
        flagKeys = [allMatches.schema.find("base_PixelFlags_flag_%s" % flag).key
                    for flag in ("saturated", "cr", "bad", "edge")]
        nMatchesRequired = 2

        psfSnrKey = allMatches.schema.find("base_PsfFlux_snr").key
        psfMagKey = allMatches.schema.find("base_PsfFlux_mag").key
        psfMagErrKey = allMatches.schema.find("base_PsfFlux_magerr").key
        extendedKey = allMatches.schema.find("base_ClassificationExtendedness_value").key

        def goodFilter(cat, goodSnr=3):
            if len(cat) < nMatchesRequired:
                return False
            for flagKey in flagKeys:
                if cat.get(flagKey).any():
                    return False
            if not np.isfinite(cat.get(psfMagKey)).all():
                return False
            psfSnr = np.median(cat.get(psfSnrKey))
            # Note that this also implicitly checks for psfSnr being non-nan.
            return psfSnr >= goodSnr

        goodMatches = allMatches.where(goodFilter)

        # Filter further to a limited range in S/N and extendedness
        # to select bright stars.
        safeMaxExtended = 1.0

        def safeFilter(cat):
            psfSnr = np.median(cat.get(psfSnrKey))
            extended = np.max(cat.get(extendedKey))
            return psfSnr >= safeSnr and extended < safeMaxExtended

        safeMatches = goodMatches.where(safeFilter)

        # Pass field=psfMagKey so np.mean just gets that as its input
        self.snr = goodMatches.aggregate(np.median, field=psfSnrKey) * u.Unit('')
        self.mag = goodMatches.aggregate(np.mean, field=psfMagKey) * u.mag
        self.magrms = goodMatches.aggregate(np.std, field=psfMagKey) * u.mag
        self.magerr = goodMatches.aggregate(np.median, field=psfMagErrKey) * u.mag
        # positionRms knows how to query a group so we give it the whole thing
        # by going with the default `field=None`.
        self.dist = goodMatches.aggregate(positionRms) * u.milliarcsecond

        # These attributes are not serialized
        self.goodMatches = goodMatches
        self.safeMatches = safeMatches


def positionRms(cat):
    """Calculate the RMS for RA, Dec for a set of observations an object.

    Parameters
    ----------
    cat -- collection with a .get method
         for 'coord_ra', 'coord_dec' that returns radians.

    Returns
    -------
    pos_rms -- RMS of positions in milliarcsecond.  Float.

    This routine doesn't handle wrap-around
    """
    ra_avg, dec_avg = averageRaDecFromCat(cat)
    ra, dec = cat.get('coord_ra'), cat.get('coord_dec')
    # Approximating that the cos(dec) term is roughly the same
    #   for all observations of this object.
    ra_var = np.var(ra) * np.cos(dec_avg)**2
    dec_var = np.var(dec)
    pos_rms = np.sqrt(ra_var + dec_var)  # radians
    pos_rms = afwGeom.radToMas(pos_rms)  # milliarcsec

    return pos_rms
