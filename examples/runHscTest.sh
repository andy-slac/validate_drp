#!/bin/bash

# Setup
export OMP_NUM_THREADS=1

# Fake out the pipeline about the origin of the reference catalog
export SETUP_ASTROMETRY_NET_DATA="astrometry_net_data sdss-dr9-fink-v5b"
export ASTROMETRY_NET_DATA_DIR=${VALIDATION_DATA_HSC_DIR}/sdss-dr9-fink-v5b

REPO='data_hsc'
RERUN=20170105

PRODUCT_DIR="${VALIDATE_DRP_DIR}"

CAMERA=Hsc
YAMLCONFIG="${PRODUCT_DIR}"/examples/"${CAMERA}".yaml

DATA_DIR=${VALIDATION_DATA_HSC_DIR}
CALIB_DIR=${VALIDATION_DATA_HSC_DIR}/CALIB

# Ingest raw data into repo
mkdir -p ${REPO}
ln -s ${CALIB_DIR} ${REPO}/CALIB
echo lsst.obs.hsc.HscMapper > ${REPO}/_mapper
ingestImages.py ${REPO} --mode=link ${VALIDATION_DATA_HSC_DIR}/'raw/*.fits'

ALL_VISITS=903332^903340^903982^904006^904350^904378^904828^904846

# Heavy lifting
singleFrameDriver.py ${REPO} --calib ${CALIB_DIR} --rerun ${RERUN} --job singleFrame --cores 16 --id visit=${ALL_VISITS}
makeDiscreteSkyMap.py ${REPO} --rerun ${RERUN} --id ccd=0..103 visit=${ALL_VISITS}
# makeDiscreteSkyMap INFO: tract 0 has corners (321.714, -1.294), (318.915, -1.294), (318.915, 1.504), (321.714, 1.504) (RA, Dec deg) and 15 x 15 patches


# Run astrometry check on src
OUTPUT="${REPO}"/rerun/"${RERUN}"
echo "validating"
validateDrp.py "${OUTPUT}" --configFile "${YAMLCONFIG}" "$@"

# 2017-01-03  Activate the following coadd and multi-band runs in a future push.
# coaddDriver.py ${REPO} --rerun ${RERUN} --job coadd --cores 16 --id tract=0 filter=HSC-I --selectId ccd=0..103 visit=903982^904006^904828^904846
# coaddDriver.py ${REPO} --rerun ${RERUN} --job coadd --cores 16 --id tract=0 filter=HSC-R --selectId ccd=0..103 visit=903332^903340
# coaddDriver.py ${REPO} --rerun ${RERUN} --job coadd --cores 16 --id tract=0 filter=HSC-Y --selectId ccd=0..103 visit=904350^904378
# multiBandDriver.py ${REPO} --rerun ${RERUN} --job multiband --cores 16 --id tract=0 filter=HSC-R^HSC-I^HSC-Y -C multiband-config.py
