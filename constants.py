import os

UBER_USER = os.environ.get('UBER_USER') or ""
UBER_PASS = os.environ.get('UBER_PASS') or ""

## --- PLATFORMS --- ##
SERVER_PLATFORMS = ["UBUNTU","CENTOS","DEBIAN","WIN","OSX","MAC", "SUSE", "OEL"]
MOBILE_PLATFORMS = ["CBLITE", "CBLITEIOS", "CEN7", "CEN006", "ANDROID","IOS", "JAVA", "WINDOWS", "MONO", "MACOSX"]
SDK_PLATFORMS= [".NET","JAVA","LIBC","NODE"]
MOBILE_VERSION = ["1.1.0", "1.2.0", "1.3", "1.4"]


## --- FEATURES --- ##
SERVER_FEATURES = [
    "LWW-LWW",
    "RBAC-RBAC",
    "PLASMA-PLASMA",
    "IMPORT-IMPORT_EXPORT",
    "EXPORT-IMPORT_EXPORT",
    "CONVERG-MOBILE_CONVERGENCE",
    "ANALYTIC-ANALYTICS",
    "EPHEM-EPHEMERAL",
    "AUTO-AUTO_FAILOVER",
    "FAST-FAST_FAILOVER",
    "SYSTEST-SYSTEST",
    "SYSTEM-SYSTEST",
    "SUBDOC-SUBDOC",
    "FTS-FTS",
    "MOBILEUPGRADE-MOBILE_UPGRADE",
    "EEONLY-EEONLY",
    "SDK-SDK",
    "MOBILE-MOBILE",
    "CERTIFY-OS_CERTIFY",
    "BREAKPAD-BREAKPAD",
    "CBSGW-SYNCGW",
    "SYNC-MOBILE",
    "RZA-RZA",
    "GEO-GEO",
    "EPENG-EP",
    "SECU-SECURITY",
    "TUNABLE-TUNABLE",
    "2I_REBALANCE-2I_REBALANCE",
    "2I-2I_MOI",
    "NSERV-NSERV",
    "RQG-RQG",
    "N1QL-QUERY",
    "TUQ-QUERY",
    "VIEW-VIEW",
    "QUERY-QUERY",
    "GOXDCR-GOXDCR",
    "FOREST-FORESTDB",
    "XDCR-XDCR",
    "REB-NSERV",
    "PAUSE-NSERV",
    "BACK-BACKUP_RECOVERY",
    "RECOV-BACKUP_RECOVERY",
    "UPGRADE-UPGRADE",
    "UPGRA-UPGRADE",
    "TRANSFER-TOOLS",
    "CLI-CLI",
    "_UI-UI",
    "TOOLS-TOOLS",
    "IBR-TOOLS",
    "CONNECTION-TOOLS",
    "SANITY-SANITY",
    "SANIT-SANITY",
    "SMOKE-SANITY",
    "DCP-EP",
    "FAILOVER-NSERV",
    "UNIT-UNIT"
]
MOBILE_FEATURES = ["FUNCT-FUNCTIONAL",
                   "UPGR-UPGRADE",
                   "SANITY-SANITY",
                   "BUILD-BUILD",
                   "UNIT-UNIT",
                   "CLIENT-CLIENT",
                   "LISTENER-LISTENER",
                   "NODE-NODE"]
SDK_FEATURES = [
    "LONGEVITY-STRESS",
    "SITUATIONAL-SITUATIONAL",
    "FEATURE-FEATURE",
    "CORE-FEATURE",
    "SNAPSHOT-CLIENT",
    "CLIENT-CLIENT"
]

BUILD_FEATURES = ["SANITY-BUILD_SANITY",
                   "UNIX-UNIT",
                   "UNIT-UNIT"]

#feature-libcouchbase-core-win/

## ---  VIEWS --- ##
SERVER_VIEW = {"urls" : [ "http://qa.sc.couchbase.com", "http://sdkbuilds.sc.couchbase.com/view/JAVA/job/server-build-test-java/job/centos-java-sdk-watson/", "http://sdkbuilds.sc.couchbase.com/view/.NET/job/server-build-test-net/job/centos-net-sdk-watson/", "http://sdkbuilds.sc.couchbase.com/view/GO/job/server-build-test-go/job/centos-go-sdk-watson/", "http://sdkbuilds.sc.couchbase.com/view/LCB/job/server-build-test-lcb/job/centos-lcb-sdk-watson/", "http://sdkbuilds.sc.couchbase.com/view/JAVA/job/server-build-test-java/job/centos-java-sdk-spock/", "http://sdkbuilds.sc.couchbase.com/view/.NET/job/server-build-test-net/job/centos-net-sdk-spock/", "http://sdkbuilds.sc.couchbase.com/view/GO/job/server-build-test-go/job/centos-go-sdk-spock/", "http://sdkbuilds.sc.couchbase.com/view/LCB/job/server-build-test-lcb/job/centos-lcb-sdk-spock/", "http://qa.sc.couchbase.com/view/OS%20Certification/", "http://uberjenkins.sc.couchbase.com:8080/"],
               "platforms": SERVER_PLATFORMS,
               "features": SERVER_FEATURES,
               "bucket": "server"}
MOBILE_VIEW = {"urls" : ["http://uberjenkins.sc.couchbase.com:8080/"],
               "platforms": MOBILE_PLATFORMS,
               "features": MOBILE_FEATURES,
               "bucket": "mobile"}
SDK_VIEW    = {"urls" : [],
               "platforms": SDK_PLATFORMS,
               "features": SDK_FEATURES,
               "bucket": "sdk"}
BUILD_VIEW = {"urls": ["http://cv.jenkins.couchbase.com/view/scheduled-unit-tests/job/unit-simple-test/", "http://server.jenkins.couchbase.com/job/build_sanity_matrix/", "http://server.jenkins.couchbase.com/job/watson-unix/"],
              "platforms": SERVER_PLATFORMS,
              "features": BUILD_FEATURES,
              "bucket": "build"}

VIEWS = [MOBILE_VIEW, SERVER_VIEW, BUILD_VIEW]
BUILDER_URLS = ["http://server.jenkins.couchbase.com/job/couchbase-server-build/",
                "http://server.jenkins.couchbase.com/job/watson-build/"]

CHANGE_LOG_URL = "http://172.23.123.43:8282/changelog"

## misc
DEFAULT_BUILD = "0.0.0-xxxx"
EXCLUDED = []

P0 = "P0"
P1 = "P1"
P2 = "P2"

