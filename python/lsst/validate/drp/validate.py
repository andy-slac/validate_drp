# LSST Data Management System
# Copyright 2008-2016 AURA/LSST.
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
"""Main driver functions for metric measurements, plotting, specification
grading, and persistence.
"""

from __future__ import print_function, absolute_import
from builtins import object

from textwrap import TextWrapper

from lsst.validate.base import Job

from .util import repoNameToPrefix
from .matchreduce import MatchedMultiVisitDataset
from .photerrmodel import PhotometricErrorModel
from .astromerrmodel import AstrometricErrorModel
from .calcsrd import (AMxMeasurement, AFxMeasurement, ADxMeasurement,
                      PA1Measurement, PA2Measurement, PF1Measurement,
                      TExMeasurement)
from .plot import (plotAMx, plotPA1, plotPhotometryErrorModel,
                   plotAstrometryErrorModel)


__all__ = ['run', 'runOneFilter']


class bcolors(object):
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def run(repo, dataIds, metrics, outputPrefix=None, level="design", verbose=False, **kwargs):
    """Main entrypoint from ``validateDrp.py``.

    Runs multiple filters, if necessary, through repeated calls to `runOneFilter`.
    Assesses results against SRD specs at specified `level`.

    Arguments
    ---------
    repo : `str`
        The repository.  This is generally the directory on disk
        that contains the repository and mapper.
    dataIds : `list` of `dict`
        List of butler data IDs of Image catalogs to compare to reference.
        The calexp cpixel image is needed for the photometric calibration.
    metrics : `dict` or `collections.OrderedDict`
        Dictionary of `lsst.validate.base.Metric` instances. Typically this is
        data from ``validate_drp``\ 's ``metrics.yaml`` and loaded with
        `lsst.validate.base.load_metrics`.
    outputPrefix : `str`, optional
        Specify the beginning filename for output files.
        The name of each filter will be appended to outputPrefix.
    level : `str`, optional
        The level of the specification to check: "design", "minimum", "stretch".
    verbose : `bool`
        Provide detailed output.

    Notes
    -----
    Names of plot files or JSON file are generated based on repository name,
    unless overriden by specifying `ouputPrefix`.
    E.g., Analyzing a repository "CFHT/output"
        will result in filenames that start with "CFHT_output_".
    The filter name is added to this prefix.  If the filter name has spaces,
        there will be annoyance and sadness as those spaces will appear in the filenames.
    """

    allFilters = set([d['filter'] for d in dataIds])

    if outputPrefix is None:
        outputPrefix = repoNameToPrefix(repo)

    jobs = {}
    for filterName in allFilters:
        # Do this here so that each outputPrefix will have a different name for each filter.
        thisOutputPrefix = "%s_%s_" % (outputPrefix.rstrip('_'), filterName)
        theseVisitDataIds = [v for v in dataIds if v['filter'] == filterName]
        job = runOneFilter(repo, theseVisitDataIds, metrics,
                           outputPrefix=thisOutputPrefix,
                           verbose=verbose, filterName=filterName,
                           **kwargs)
        jobs[filterName] = job

    passedCurrent = True  # Trip to false for failure in the 'current' level
    currentTestCount = 0
    currentFailCount = 0

    for filterName, job in jobs.items():
        print('')
        print(bcolors.BOLD + bcolors.HEADER + "=" * 65 + bcolors.ENDC)
        print(bcolors.BOLD + bcolors.HEADER + '{0} band summary'.format(filterName) + bcolors.ENDC)
        print(bcolors.BOLD + bcolors.HEADER + "=" * 65 + bcolors.ENDC)

        for specName in job.spec_levels:
            passed = True

            measurementCount = 0
            failCount = 0
            for m in job.measurements:
                if m.quantity is None:
                    continue
                measurementCount += 1
                if not m.check_spec(specName):
                    passed = False
                    failCount += 1

            if specName == level:
                currentTestCount += measurementCount
                currentFailCount += failCount
                if not passed:
                    passedCurrent = False

            if passed:
                print('Passed {level:12s} {count:d} measurements'.format(
                    level=specName, count=measurementCount))
            else:
                msg = 'Failed {level:12s} {failCount} of {count:d} failed'.format(
                    level=specName, failCount=failCount, count=measurementCount)
                print(bcolors.FAIL + msg + bcolors.ENDC)

        print(bcolors.BOLD + bcolors.HEADER + "=" * 65 + bcolors.ENDC + '\n')

    # print summary against current spec level
    print(bcolors.BOLD + bcolors.HEADER + "=" * 65 + bcolors.ENDC)
    print(bcolors.BOLD + bcolors.HEADER + '{0} level summary'.format(level) + bcolors.ENDC)
    print(bcolors.BOLD + bcolors.HEADER + "=" * 65 + bcolors.ENDC)
    if passedCurrent:
        print('PASSED ({count:d}/{count:d} measurements)'.format(
            count=measurementCount))
    else:
        msg = 'FAILED ({failCount:d}/{count:d} measurements)'.format(
            failCount=currentFailCount, count=measurementCount)
        print(bcolors.FAIL + msg + bcolors.ENDC)
    print(bcolors.BOLD + bcolors.HEADER + "=" * 65 + bcolors.ENDC)


def runOneFilter(repo, visitDataIds, metrics, brightSnr=100,
                 makePrint=True, makePlot=True, makeJson=True,
                 filterName=None, outputPrefix=None,
                 verbose=False,
                 **kwargs):
    """Main executable for the case where there is just one filter.

    Plot files and JSON files are generated in the local directory
        prefixed with the repository name (where '_' replace path separators),
    unless overriden by specifying `outputPrefix`.
    E.g., Analyzing a repository "CFHT/output"
        will result in filenames that start with "CFHT_output_".

    Parameters
    ----------
    repo : string
        The repository.  This is generally the directory on disk
        that contains the repository and mapper.
    dataIds : list of dict
        List of `butler` data IDs of Image catalogs to compare to reference.
        The `calexp` cpixel image is needed for the photometric calibration.
    metrics : `dict` or `collections.OrderedDict`
        Dictionary of `lsst.validate.base.Metric` instances. Typically this is
        data from ``validate_drp``\ 's ``metrics.yaml`` and loaded with
        `lsst.validate.base.load_metrics`.
    brightSnr : float, optional
        Minimum SNR for a star to be considered bright
    makePrint : bool, optional
        Print calculated quantities (to stdout).
    makePlot : bool, optional
        Create plots for metrics.  Saved to current working directory.
    makeJson : bool, optional
        Create JSON output file for metrics.  Saved to current working directory.
    outputPrefix : str, optional
        Specify the beginning filename for output files.
    filterName : str, optional
        Name of the filter (bandpass).
    verbose : bool, optional
        Output additional information on the analysis steps.
    """
    if outputPrefix is None:
        outputPrefix = repoNameToPrefix(repo)

    matchedDataset = MatchedMultiVisitDataset(repo, visitDataIds,
                                              verbose=verbose)
    photomModel = PhotometricErrorModel(matchedDataset)
    astromModel = AstrometricErrorModel(matchedDataset)
    linkedBlobs = {'photomModel': photomModel, 'astromModel': astromModel}

    job = Job(blobs=[matchedDataset, photomModel, astromModel])

    for x in (1, 2, 3):
        amxName = 'AM{0:d}'.format(x)
        afxName = 'AF{0:d}'.format(x)
        adxName = 'AD{0:d}'.format(x)

        AMxMeasurement(metrics[amxName], matchedDataset, filterName,
                       job=job, linkedBlobs=linkedBlobs, verbose=verbose)

        for specName in metrics[afxName].get_spec_names(filter_name=filterName):
            AFxMeasurement(metrics[afxName], matchedDataset,
                           job.get_measurement(amxName), filterName, specName,
                           job=job, linkedBlobs=linkedBlobs, verbose=verbose)

            ADxMeasurement(metrics[adxName], matchedDataset,
                           job.get_measurement(amxName), filterName, specName,
                           job=job, linkedBlobs=linkedBlobs, verbose=verbose)

    PA1Measurement(metrics['PA1'], matchedDataset, filterName,
                   job=job, linkedBlobs=linkedBlobs,
                   verbose=verbose)

    for specName in metrics['PA2'].get_spec_names(filter_name=filterName):
        PA2Measurement(metrics['PA2'], matchedDataset,
                       pa1=job.get_measurement('PA1'), filter_name=filterName,
                       spec_name=specName, verbose=verbose,
                       job=job, linkedBlobs=linkedBlobs)

    for specName in metrics['PF1'].get_spec_names(filter_name=filterName):
        PF1Measurement(metrics['PF1'], matchedDataset,
                       job.get_measurement('PA1'),
                       filterName, specName, verbose=verbose,
                       job=job, linkedBlobs=linkedBlobs)

    for x in (1, 2):
        texName = 'TE{0:d}'.format(x)
        TExMeasurement(metrics[texName], matchedDataset, filterName,
                       job=job, linkedBlobs=linkedBlobs, verbose=verbose)

    job.write_json(outputPrefix.rstrip('_') + '.json')

    if makePlot:
        if job.get_measurement('AM1').quantity is not None:
            plotAMx(job.get_measurement('AM1'),
                    job.get_measurement('AF1', spec_name='design'),
                    filterName, amxSpecName='design',
                    outputPrefix=outputPrefix)
        if job.get_measurement('AM2').quantity is not None:
            plotAMx(job.get_measurement('AM2'),
                    job.get_measurement('AF2', spec_name='design'),
                    filterName, amxSpecName='design',
                    outputPrefix=outputPrefix)
        if job.get_measurement('AM3').quantity is not None:
            plotAMx(job.get_measurement('AM3'),
                    job.get_measurement('AF3', spec_name='design'),
                    filterName, amxSpecName='design',
                    outputPrefix=outputPrefix)

        plotPA1(job.get_measurement('PA1'), outputPrefix=outputPrefix)

        plotPhotometryErrorModel(matchedDataset, photomModel,
                                 filterName=filterName,
                                 outputPrefix=outputPrefix)

        plotAstrometryErrorModel(matchedDataset, astromModel,
                                 outputPrefix=outputPrefix)

    if makePrint:
        print(bcolors.BOLD + bcolors.HEADER + "=" * 65 + bcolors.ENDC)
        print(bcolors.BOLD + bcolors.HEADER +
              '{band} band metric measurements'.format(band=filterName) +
              bcolors.ENDC)
        print(bcolors.BOLD + bcolors.HEADER + "=" * 65 + bcolors.ENDC)

        wrapper = TextWrapper(width=65)

        for metricName in metrics:
            metric = metrics[metricName]
            print(bcolors.HEADER + '{name} - {reference}'.format(
                name=metric.name, reference=metric.reference))
            print(wrapper.fill(bcolors.ENDC + '{description}'.format(
                description=metric.description).strip()))

            for specName in metric.get_spec_names(filter_name=filterName):
                try:
                    m = job.get_measurement(metricName,
                                            spec_name=specName,
                                            filter_name=filterName)
                except RuntimeError:
                    print('\tSkipped {specName:12s} no spec'.format(
                        specName=specName))
                    continue

                if m.quantity is None:
                    print('\tSkipped {specName:12s} no measurement'.format(
                        specName=specName))
                    continue

                spec = metric.get_spec(specName, filter_name=filterName)
                passed = m.check_spec(specName)
                if passed:
                    prefix = bcolors.OKBLUE + '\tPassed '
                else:
                    prefix = bcolors.FAIL + '\tFailed '
                infoStr = '{specName:12s} {meas:.4g} {op} {spec:.4g}'.format(
                    specName=specName,
                    meas=m.quantity,
                    op=metric.operator_str,
                    spec=spec.quantity)
                print(prefix + infoStr + bcolors.ENDC)

    return job
