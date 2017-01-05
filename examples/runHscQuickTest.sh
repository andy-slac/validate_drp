#!/bin/bash

# USES DATA IN ci_hsc

# Setup
export OMP_NUM_THREADS=1

# Fake out the pipeline about the origin of the reference catalog
export SETUP_ASTROMETRY_NET_DATA="astrometry_net_data sdss-dr9-fink-v5b"
export ASTROMETRY_NET_DATA_DIR=${CI_HSC_DIR}/sdss-dr9-fink-v5b

REPO='data_hsc_quick'
RERUN=20170105

PRODUCT_DIR="${VALIDATE_DRP_DIR}"

CAMERA=HscQuick
YAMLCONFIG="${PRODUCT_DIR}"/examples/"${CAMERA}".yaml

# DATA_DIR=${VALIDATION_DATA_HSC_DIR}
DATA_DIR=${CI_HSC_DIR}
CALIB_DIR=${CI_HSC_DIR}/CALIB

# Ingest raw data into repo
mkdir -p ${REPO}
ln -s ${CALIB_DIR} ${REPO}/CALIB
echo lsst.obs.hsc.HscMapper > ${REPO}/_mapper
ingestImages.py ${REPO} --mode=link ${CI_HSC_DIR}/'raw/*.fits'

ALL_VISITS= 903334^903336^903338^903342^903344^903346^903986^903988^903990^904010^904014

# The available images in ci_hsc are
# visit|filter|ccd
# 903334|HSC-R|16
# 903334|HSC-R|22
# 903334|HSC-R|23
# 903334|HSC-R|100
# 903336|HSC-R|17
# 903336|HSC-R|24
# 903338|HSC-R|18
# 903338|HSC-R|25
# 903342|HSC-R|4
# 903342|HSC-R|10
# 903342|HSC-R|100
# 903344|HSC-R|0
# 903344|HSC-R|5
# 903344|HSC-R|11
# 903346|HSC-R|1
# 903346|HSC-R|6
# 903346|HSC-R|12
# 903986|HSC-I|16
# 903986|HSC-I|22
# 903986|HSC-I|23
# 903986|HSC-I|100
# 903988|HSC-I|16
# 903988|HSC-I|17
# 903988|HSC-I|23
# 903988|HSC-I|24
# 903990|HSC-I|18
# 903990|HSC-I|25
# 904010|HSC-I|4
# 904010|HSC-I|10
# 904010|HSC-I|100
# 904014|HSC-I|1
# 904014|HSC-I|6
# 904014|HSC-I|12

# Heavy lifting
singleFrameDriver.py ${REPO} --calib ${CALIB_DIR} --rerun ${RERUN} --job singleFrame --cores 16 --id visit=${ALL_VISITS}
makeDiscreteSkyMap.py ${REPO} --rerun ${RERUN} --id ccd=0..103 visit=${ALL_VISITS}
# makeDiscreteSkyMap INFO: tract 0 has corners (321.166, -0.594), (320.606, -0.594), (320.606, -0.034), (321.166, -0.034) (RA, Dec deg) and 3 x 3 patches
### coaddDriver.py ${REPO} --rerun ${RERUN} --job coadd --cores 16 --id tract=0 filter=HSC-I --selectId ccd=0..103 visit=903982^904006^904828^904846
### coaddDriver.py ${REPO} --rerun ${RERUN} --job coadd --cores 16 --id tract=0 filter=HSC-R --selectId ccd=0..103 visit=903332^903340
### coaddDriver.py ${REPO} --rerun ${RERUN} --job coadd --cores 16 --id tract=0 filter=HSC-Y --selectId ccd=0..103 visit=904350^904378
### multiBandDriver.py ${REPO} --rerun ${RERUN} --job multiband --cores 16 --id tract=0 filter=HSC-R^HSC-I^HSC-Y -C multiband-config.py

# Run astrometry check on src
OUTPUT="${REPO}"/rerun/"${RERUN}"
echo "validating"
validateDrp.py "${OUTPUT}" --configFile "${YAMLCONFIG}" "$@"

