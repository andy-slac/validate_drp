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

from __future__ import print_function, absolute_import

import numpy as np
import astropy.units as u

from lsst.validate.base import MeasurementBase


class PF1Measurement(MeasurementBase):
    """Measurement of PF1: fraction of samples between median RMS (PA1) and
    PA2 specification.

    Parameters
    ----------
    metric : `lsst.validate.base.Metric`
        A PF1 `~lsst.validate.base.Metric` instance.
    matchedDataset : lsst.validate.drp.matchreduce.MatchedMultiVisitDataset
    pa1 : PA1Measurement
        A PA1 measurement instance.
    filter_name : str
        filter_name (filter name) used in this measurement (e.g., `'r'`).
    spec_name : str
        Name of a specification level to measure against (e.g., design,
        minimum, stretch).
    verbose : bool, optional
        Output additional information on the analysis steps.
    job : :class:`lsst.validate.drp.base.Job`, optional
        If provided, the measurement will register itself with the Job
        object.
    linkedBlobs : dict, optional
        A `dict` of additional blobs (subclasses of BlobBase) that
        can provide additional context to the measurement, though aren't
        direct dependencies of the computation (e.g., `matchedDataset).

    Notes
    -----
    The LSST Science Requirements Document (LPM-17) is commonly referred
    to as the SRD.  The SRD puts a limit that no more than PF1 % of difference
    will vary by more than PA2 millimag.  The design, minimum, and stretch
    goals are PF1 = (10, 20, 5) % at PA2 = (15, 15, 10) millimag following
    LPM-17 as of 2011-07-06, available at http://ls.st/LPM-17.
    """

    def __init__(self, metric, matchedDataset, pa1, filter_name, spec_name,
                 linkedBlobs=None, job=None, verbose=False):
        MeasurementBase.__init__(self)
        self.filter_name = filter_name
        self.spec_name = spec_name  # spec-dependent measure because of PF1 dep
        self.metric = metric

        pa2spec = self.metric.get_spec(spec_name, filter_name=self.filter_name).\
            PA2.get_spec(spec_name, filter_name=self.filter_name)
        self.register_parameter('pa2', datum=pa2spec.datum)

        self.matchedDataset = matchedDataset

        # Add external blob so that links will be persisted with
        # the measurement
        if linkedBlobs is not None:
            for name, blob in linkedBlobs.items():
                setattr(self, name, blob)

        # Use first random sample from original PA1 measurement
        magDiffs = pa1.magDiff[0, :]

        self.quantity = 100 * np.mean(np.abs(magDiffs) > self.pa2) * u.Unit('')

        if job:
            job.register_measurement(self)
