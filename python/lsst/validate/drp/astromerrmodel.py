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
"""Analytic astrometric accuracy model.
"""

from __future__ import print_function, absolute_import

import astropy.units as u
import numpy as np
from scipy.optimize import curve_fit

from lsst.validate.base import BlobBase


__all__ = ['astromErrModel', 'fitAstromErrModel', 'AstrometricErrorModel']


def astromErrModel(snr, theta=1000, sigmaSys=10, C=1, **kwargs):
    """Calculate expected astrometric uncertainty based on SNR.

    mas = C*theta/SNR + sigmaSys

    Parameters
    ----------
    snr : `numpy.ndarray` or `astropy.unit.Quantity`
        S/N of photometric measurements (dimensionless).
    theta : `float`, `numpy.ndarray` or `astropy.unit.Quantity`, optional
        Seeing (default: milliarcsec).
    sigmaSys : `astropy.unit.Quantity`
        Systematic error floor (default: milliarcsec).
    C : `float`
        Scaling factor (dimensionless)

    Returns
    -------
    sigma : `astropy.unit.Quantity`
        Expected astrometric uncertainty with the same dimensions as ``snr``.
        Units will be those of theta and sigmaSys.

    Notes
    -----
    ``theta`` and ``sigmaSys`` must be given in the same units.
    Typically choices might be any of arcsec, milli-arcsec, or radians.
    The default values are reasonable astronominal values in milliarcsec.
    But the only thing that matters is that they're the same.
    """
    return C*theta/snr + sigmaSys


def fitAstromErrModel(snr, dist):
    """Fit model of astrometric error from LSST Overview paper

    Parameters
    ----------
    snr : `np.ndarray` or `astropy.unit.Quantity`
        Signal-to-noise ratio of photometric observations (dimensionless).
    dist : `np.ndarray` or `astropy.unit.Quantity`
        Scatter in measured positions (default: millarcsec)

    Returns
    -------
    params : `dict`
        Fitted model parameters. Fields are:

        - ``C``: Model scale factor (dimensionless).
        - ``theta``: Seeing (default: milliarcsec).
        - ``sigmaSys``: Systematic astrometric uncertainty
          (default: milliarcsec).
    """
    # Note that C is fixed to 1.
    p0 = [1,  # theta
          0.01]  # sigmaSys
    if isinstance(dist, u.Quantity):
        dist = dist.to(u.marcsec).value
    if isinstance(snr, u.Quantity):
        snr = snr.value
    fit_params, fit_param_covariance = curve_fit(astromErrModel, snr, dist,
                                                 p0=p0)

    params = {'C': 1 * u.Unit(''),
              'theta': fit_params[0] * u.marcsec,
              'sigmaSys': fit_params[1] * u.marcsec}
    return params


class AstrometricErrorModel(BlobBase):
    """Serializable model of astrometry errors across multiple visits.

    .. math::

       \mathrm{astromRms} = C \theta / \mathrm{SNR} + \sigma_\mathrm{sys}

    Parameters
    ----------
    matchedMultiVisitDataset : `MatchedMultiVisitDataset`
        A dataset containing matched statistics for stars across multiple
        visits.
    brightSnr : `float` or `astropy.unit.Quantity`, optional
        Minimum SNR for a star to be considered "bright" (dimensionless).
    medianRef : `float` or `astropy.unit.Quantity`, optional
        Median reference astrometric scatter (default: milliarcsecond).
    matchRef : int, optional
        Should match at least matchRef number of stars (dimensionless).

    Attributes
    ----------
    brightSnr : float
        Threshold SNR for bright sources used in this model.
    C : float
        Model scaling factor.
    theta : float
        Seeing (milliarcsecond).
    sigmaSys : float
        Systematic error floor (milliarcsecond).
    astromRms : float
        Astrometric scatter (RMS) for good stars (milliarcsecond).

    Notes
    -----
    The scatter and match defaults appropriate to SDSS are the defaults
    for ``medianRef`` and ``matchRef``.

    For SDSS, stars with mag < 19.5 should be completely well measured.
    """

    name = 'AnalyticAstrometryModel'

    def __init__(self, matchedMultiVisitDataset, brightSnr=100,
                 medianRef=100, matchRef=500):
        BlobBase.__init__(self)

        # FIXME add description field to blobs
        # self._doc['doc'] \
        #     = "Astrometric astrometry model: mas = C*theta/SNR + sigmaSys"

        if not isinstance(brightSnr, u.Quantity):
            brightSnr = brightSnr * u.Unit('')
        if not isinstance(medianRef, u.Quantity):
            medianRef = medianRef * u.marcsec

        self._compute(
            matchedMultiVisitDataset.snr,
            matchedMultiVisitDataset.dist,
            len(matchedMultiVisitDataset.goodMatches),
            brightSnr, medianRef, matchRef)

    def _compute(self, snr, dist, nMatch, brightSnr, medianRef, matchRef):
        median_dist = np.median(dist)
        msg = 'Median value of the astrometric scatter - all magnitudes: ' \
              '{0:.3f}'
        print(msg.format(median_dist))

        bright = np.where(snr > brightSnr)
        astromScatter = np.median(dist[bright])
        msg = 'Astrometric scatter (median) - snr > {0:.1f} : {1:.1f}'
        print(msg.format(brightSnr, astromScatter))

        fit_params = fitAstromErrModel(snr[bright], dist[bright])

        if astromScatter > medianRef:
            msg = 'Median astrometric scatter {0:.1f} is larger than ' \
                  'reference : {1:.1f}'
            print(msg.format(astromScatter, medianRef))
        if nMatch < matchRef:
            msg = 'Number of matched sources {0:d} is too small ' \
                  '(should be > {1:d})'
            print(msg.format(nMatch, matchRef))

        self.register_datum(
            'brightSnr',
            quantity=brightSnr,
            label='Bright SNR',
            description='Threshold in SNR for bright sources used in this '
                        'model')
        self.register_datum(
            'C',
            quantity=fit_params['C'],
            description='Scaling factor')
        self.register_datum(
            'theta',
            quantity=fit_params['theta'],
            label='theta',
            description='Seeing')
        self.register_datum(
            'sigmaSys',
            quantity=fit_params['sigmaSys'],
            label='sigma(sys)',
            description='Systematic error floor')
        self.register_datum(
            'astromRms',
            quantity=astromScatter,
            label='RMS',
            description='Astrometric scatter (RMS) for good stars')
