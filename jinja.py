import re
import sys
import time
import datetime
import pydash
import subprocess
import os
import requests
import hashlib
import json
from threading import Thread
from couchbase.bucket import Bucket, LOCKMODE_WAIT
from couchbase.n1ql import N1QLQuery
from constants import *
from urlparse import urlparse
from test_collector import TestCaseCollector

import sys
reload(sys)
sys.setdefaultencoding('utf8')

UBER_USER = os.environ.get('UBER_USER') or ""
UBER_PASS = os.environ.get('UBER_PASS') or ""


JOBS = {}
ALLJOBS = {}
CLIENTS = {}
HOST = '172.23.98.63'
TEST_CASE_COLLECTOR = TestCaseCollector()
if len(sys.argv) == 2:
    HOST = sys.argv[1]

def createClients():
    for view in VIEWS:
        bucket = view['bucket']
        if bucket == "build":
            continue
        try:
            client = Bucket("couchbase://{0}/{1}".format(HOST, bucket), lockmode=LOCKMODE_WAIT,username='Administrator',password='password')
            CLIENTS[bucket] = client
        except Exception:
            print "Error while connecting to {0}/{1}".format(HOST, bucket)
    try:
        client = Bucket("couchbase://{0}/{1}".format(HOST, "builds"), lockmode=LOCKMODE_WAIT,username='Administrator',password='password')
        CLIENTS['builds'] = client
    except Exception:
        print "Error while connecting to {0}/{1}".format(HOST, "builds")
    try:
        client = Bucket("couchbase://{0}/{1}".format(HOST, "QE-Test-Suites"), lockmode=LOCKMODE_WAIT,username='Administrator',password='password')
        CLIENTS['testSuites'] = client
    except Exception:
        print "Error while connecting to {0}/{1}".format(HOST, "QE-Test-Suites")

def get_build_document(build, type):
    client = CLIENTS['builds']
    try:
        doc = client.get(build)
        return doc.value
    except Exception:
        doc = {
            "build": build,
            "totalCount": 0,
            "failCount": 0,
            "type": type,
            "os": {}
        }
        if type=='server-test':
            platform = SERVER_PLATFORMS
            features = SERVER_FEATURES
        elif type == 'mobile':
            platform = MOBILE_PLATFORMS
            features = MOBILE_FEATURES
        elif type == 'sdk':
            platform = SDK_PLATFORMS
            features = SDK_FEATURES
        elif type == 'build':
            doc['type'] = 'server'
            platform =  SERVER_PLATFORMS
            features = BUILD_FEATURES
        for _platform in platform:
            _features = {}
            for _feature in features:
                _features[_feature.split('-')[1]] = {}
            doc['os'][_platform] = _features
        return doc

def store_build_details(build_document, type):
    build = build_document['build']
    doc = get_build_document(build, type)
    os = build_document['os']
    component = build_document['component']
    name = build_document['name']
    sub_component = build_document['subComponent'] if "subComponent" in build_document else ""
    implemented_in = getImplementedIn(component, sub_component)
    if (type not in ALLJOBS):
        ALLJOBS[type] = {}
    if os not in ALLJOBS[type]:
        ALLJOBS[type][os] = {}
    if component not in ALLJOBS[type][os]:
        ALLJOBS[type][os][component] = {}
    ALLJOBS[type][os][component][name] = {
        "totalCount": build_document['totalCount'],
        "url": build_document['url'],
        "priority": build_document['priority'],
        "implementedIn": implemented_in
    }
    if os not in doc['os']:
        doc['os'][os] = {}
    if component not in doc['os'][os]:
        doc['os'][os][component] = {}
    existing_builds = doc['os'][os][component]
    if name in existing_builds:
        build_exist = [t for t in existing_builds[name] if t['build_id'] == build_document['build_id']]
        if build_exist.__len__() != 0:
            return
    else:
        existing_builds[name] = []
    build_to_store = {
        "build_id": build_document['build_id'],
        "claim": "",
        "totalCount": build_document['totalCount'],
        "result": build_document['result'],
        "duration": build_document['duration'],
        "url": build_document['url'],
        "priority": build_document['priority'],
        "failCount": build_document['failCount'],
        "color": build_document['color'] if 'color' in build_document else '',
        "deleted": False,
        "olderBuild": False,
        "disabled": False
    }
    doc['os'][os][component][name].append(build_to_store)
    pydash.sort(doc['os'][os][component][name], key=lambda item: item['build_id'], reverse=True)
    existing_builds[name][0]['olderBuild'] = False
    for existing_build in existing_builds[name][1:]:
        existing_build['olderBuild'] = True
    get_total_fail_count(doc)
    client = CLIENTS['builds']
    try:
        client.upsert(build, doc)
    except:
        client.upsert(build, doc)


def purge_job_details(doc_id, type, disabled=False):
    client = CLIENTS[type]
    build_client = CLIENTS['builds']
    try:
        job = client.get(doc_id).value
        if 'build' not in job:
            return
        build = job['build']
        build_document = build_client.get(build)
        os = job['os']
        name = job['name']
        build_id = job['build_id']
        component = job['component']
        if(build_document['os'][os][component].__len__() == 0 or name not in build_document['os'][os][component]):
            return
        to_del_job = [t for t in build_document['os'][os][component][name] if t['build_id'] == build_id]
        if to_del_job.__len__() == 0:
            return
        to_del_job = to_del_job[0]
        if disabled and ('disabled' in to_del_job and not to_del_job['disabled']):
            to_del_job['disabled'] = True
            build_document['totalCount'] -= to_del_job['totalCount']
            build_document['failCount'] -= to_del_job['failCount']
        else:
            jobs_in_name = build_document['os'][os][component][name]

            to_del_job['deleted'] = True
            #build_document['totalCount'] -= to_del_job['totalCount']
            #build_document['failCount'] -= to_del_job['failCount']
        build_client.upsert(build, build_document)
    except Exception:
        pass

def store_existing_jobs():
    client = CLIENTS['builds']
    try:
        stored_builds = client.get("existing_builds")
        if stored_builds != ALLJOBS:
            client.upsert("existing_builds", ALLJOBS)
    except Exception:
        client.upsert("existing_builds", ALLJOBS)

def get_from_bucket_and_store_build(bucket):
    client = CLIENTS[bucket]
    builds_query = "select distinct `build` from {0} where `build` is not null order by `build`".format(bucket)
    for row in client.n1ql_query(N1QLQuery(builds_query)):
        build = row['build']
        if not build:
            continue
        jobsQuery = "select * from {0} where `build` = '{1}'".format(bucket, build)
        for job in client.n1ql_query(N1QLQuery(jobsQuery)):
            doc = job[bucket]
            store_build_details(doc, bucket)

def get_total_fail_count(document):
    totalCount = 0
    failCount = 0
    for OS, os in document['os'].items():
        for COMPONENT, component in os.items():
            for JOBNAME, jobName in component.items():
                build = pydash.find(jobName, {"olderBuild": False})
                if build:
                    totalCount += build['totalCount']
                    failCount += build['failCount']
    document['totalCount'] = totalCount
    document['failCount'] = failCount

def sanitize():
    client = CLIENTS['builds']
    query = "select meta().id from `builds` where `build` is not null"
    for row in client.n1ql_query(N1QLQuery(query)):
        build_id = row['id']
        document = client.get(build_id).value
        for OS, os in document['os'].items():
            for COMPONENT, component in os.items():
                for JOBNAME, jobName in component.items():
                    pydash.sort(jobName, key=lambda item: item['build_id'], reverse=True)
                    for build in jobName[1:]:
                        build['olderBuild'] = True
        get_total_fail_count(document)
        try:
            client.upsert(build_id, document)
        except:
            client.upsert(build_id, document)


def store_test_cases(job_details):
    """
    Store the test cases that were run as part of the Job and their results into test case repository
    :param job_details: Details of the job that was run.
    :return: nothing
    """
    # Return if the job was aborted, since no test results can be obtained from aborted runs.
    if job_details['result'] in ["ABORTED", "FAILURE"]:
        return
    url = job_details['url'] + job_details['build_id'].__str__() + "/testReport"
    test_results = getJS(url)
    if test_results is None:
        return
    if "suites" not in test_results:
        return
    for suite in test_results['suites']:
        if 'cases' not in suite:
            continue
        for case in suite['cases']:
            # if "conf_file" not in case['name']:
            #     print case['name']
            #     continue
            TEST_CASE_COLLECTOR.store_test_result(case, job_details)


def getJS(url, params = None, retry = 0, append_api_json=True):
    res = None
    try:
        if append_api_json:
            res = requests.get("%s/%s" % (url, "api/json"), params = params, timeout=15)
        else:
            res = requests.get("%s" % url, params=params, timeout=15)
        data = res.json()
        return data
    except:
        print "[Error] url unreachable: %s" % url
        res = None
        if retry:
            retry = retry - 1
            return getJS(url, params, retry)
        else:
            pass

    return res

def getAction(actions, key, value = None):

    if actions is None:
        return None

    obj = None
    keys = []
    for a in actions:
        if a is None:
            continue
        if 'keys' in dir(a):
            keys = a.keys()
        else:
            # check if new api
            if 'keys' in dir(a[0]):
                keys = a[0].keys()
        if "urlName" in keys:
            if a["urlName"]!= "robot" and a["urlName"] != "testReport" and a["urlName"] != "tapTestReport":
                continue

        if key in keys:
            if value:
                if a["name"] == value:
                    obj = a["value"]
                    break
            else:
                obj = a[key]
                break

    return obj

def getBuildAndPriority(params, isMobile = False):
    build = None
    priority = DEFAULT_BUILD

    if params:
        if not isMobile:
            build = getAction(params, "name", "version_number") or getAction(params, "name", "cluster_version") or  getAction(params, "name", "build") or  getAction(params, "name", "COUCHBASE_SERVER_VERSION") or DEFAULT_BUILD
        else:
            build = getAction(params, "name", "SYNC_GATEWAY_VERSION") or getAction(params, "name", "SYNC_GATEWAY_VERSION_OR_COMMIT") or getAction(params, "name", "COUCHBASE_MOBILE_VERSION") or getAction(params, "name", "CBL_iOS_Build")

        priority = getAction(params, "name", "priority") or P1
        if priority.upper() not in [P0, P1, P2]:
            priority = P1

    if build is None:
        return None, None

    build = build.replace("-rel","").split(",")[0]
    try:
        _build = build.split("-")
        if len(_build) == 1:
            raise Exception("Invalid Build number: {} Should follow 1.1.1-0000 naming".format(_build))

        rel, bno = _build[0], _build[1]
        # check partial rel #'s
        rlen = len(rel.split("."))
        while rlen < 3:
            rel = rel+".0"
            rlen+=1

        # verify rel, build
        m=re.match("^\d\.\d\.\d{1,5}", rel)
        if m is None:
            print "unsupported version_number: "+build
            return None, None
        m=re.match("^\d{1,10}", bno)
        if m is None:
            print "unsupported version_number: "+build
            return None, None

        build = "%s-%s" % (rel, bno.zfill(4))
    except:
        print "unsupported version_number: " + build
        return None, None

    return build, priority

def getClaimReason(actions):
    reason = ""

    if not getAction(actions, "claimed"):
        return reason # job not claimed

    reason = getAction(actions, "reason") or ""
    try:
        rep_dict={m:"<a href=\"https://issues.couchbase.com/browse/{0}\">{1}</a>".
            format(m,m) for m in re.findall(r"([A-Z]{2,4}[-: ]*\d{4,5})", reason)}
        if rep_dict:
            pattern = re.compile('|'.join(rep_dict.keys()))
            reason = pattern.sub(lambda x: rep_dict[x.group()],reason)
    except Exception as e:
        pass

    return reason
def getImplementedIn(component, subcomponent):
    client = CLIENTS['testSuites']
    query = "SELECT implementedIn from `QE-Test-Suites` where component = '{0}' and subcomponent = '{1}'".format(component.lower(), subcomponent)
    for row in client.n1ql_query(N1QLQuery(query)):
        if 'implementedIn' not in row:
            return ""
        return row['implementedIn']
    return ""

# use case# redifine 'xdcr' as 'goxdcr' 4.0.1+
def caveat_swap_xdcr(doc):
    comp = doc["component"]
    if (doc["build"] >= "4.0.1") and (comp == "XDCR"):
        comp = "GOXDCR"
    return comp

# when build > 4.1.0 and os is WIN skip VIEW, TUNEABLE, 2I, NSERV, VIEW, EP
def caveat_should_skip_win(doc):
    skip = False
    os = doc["os"]
    comp = doc["component"]
    build = doc["build"]
    if build >= "4.1.0" and os  == "WIN" and\
        (comp == "VIEW" or comp=="TUNABLE" or comp =="2I" or\
         comp == "NSERV" or comp=="VIEW" or comp=="EP"):
        if doc["name"].lower().find("w01") == 0:
            skip = True
    return skip

# when build == 4.1.0 version then skip backup_recovery
def caveat_should_skip_backup_recovery(doc):
   skip = False
   if (doc["build"].find("4.1.0") == 0) and\
      (doc["component"] == "BACKUP_RECOVERY"):
       skip = True
   return skip

def caveat_should_skip(doc):
   return caveat_should_skip_win(doc) or\
          caveat_should_skip_backup_recovery(doc)

def caveat_should_skip_mobile(doc):
   # skip mobile component loading for non cen os
   return (doc["component"].find("MOBILE") > -1) and\
             (doc["os"].find("CEN") == -1)

def isExecutor(name):
    return name.find("test_suite_executor") > -1

def skipCollect(params):
    skip_collect_u = getAction(params, "name", "SKIP_GREENBOARD_COLLECT")
    skip_collect_l = getAction(params, "name", "skip_greenboard_collect")
    return skip_collect_u or skip_collect_l

def isDisabled(job):
    status = job.get("color")
    return  status and (status == "disabled")

def purgeDisabled(job, bucket):
    client = CLIENTS[bucket]
    name = job["name"]
    bids = [b["number"] for b in job["builds"]]
    if len(bids) == 0:
        return

    high_bid = bids[0]
    for bid in xrange(high_bid):
        # reconstruct doc id
        bid = bid + 1
        oldKey = "%s-%s" % (name, bid)
        oldKey = hashlib.md5(oldKey).hexdigest()
        # purge
        try:
            purge_job_details(oldKey, bucket, disabled=True)
            client.remove(oldKey)
        except Exception as ex:
            pass # delete ok
i,j = 0 ,0
def storeTest(jobDoc, view, first_pass = True, lastTotalCount = -1, claimedBuilds = None):
    global i
    global j
    bucket = view["bucket"]

    claimedBuilds = claimedBuilds or {}
    client = CLIENTS[bucket]

    doc = jobDoc
    nameOrig = doc["name"]
    url = doc["url"]
    if url.find("sdkbuilds.couchbase") > -1:
        url = url.replace("sdkbuilds.couchbase", "sdkbuilds.sc.couchbase")

    res = getJS(url, {"depth" : 0})

    if res is None:
        return

    # do not process disabled jobs
    if isDisabled(doc):
        print("disabled {0}".format(nameOrig))
        i = i+1
        purgeDisabled(res, bucket)
        return
    j = j+1
    print("enabled {0} {1}".format(nameOrig,j))
    # operate as 2nd pass if test_executor
    if isExecutor(doc["name"]):
        first_pass = False

    buildHist = {}
    if res.get("lastBuild") is not None:

        bids = [b["number"] for b in res["builds"]]

        if isExecutor(doc["name"]):
            # include more history
            start = bids[-1]-1500
            if start > 0:
                bids = range(start, bids[0]+1)
            bids.reverse()
        elif first_pass:
            bids.reverse()  # bottom to top 1st pass
        # bids = [195289]
        for bid in bids:

            oldName = JOBS.get(doc["name"]) is not None
            if oldName and bid in JOBS[doc["name"]]:
                print "Skipping {0} as already stored".format(bid)
                continue # job already stored
            else:
                if oldName and first_pass == False:
                    JOBS[doc["name"]].append(bid)

            doc["build_id"] = bid
            res = getJS(url+str(bid), {"depth" : 0})
            if res is None:
                print "Skipping {0} as res is none".format(bid)
                continue

            if "result" not in res:
                print "Skipping {0} as result not in res is none".format(bid)
                continue

            doc["result"] = res["result"]
            doc["duration"] = res["duration"]

            if res["result"] not in ["SUCCESS", "UNSTABLE", "FAILURE", "ABORTED"]:
                print "Skipping {0} as unknown state".format(bid)
                continue # unknown result state

            actions = res["actions"]
            params = getAction(actions, "parameters")
            if skipCollect(params):
                job = getJS(url, {"depth" : 0})
                purgeDisabled(job, bucket)
                return

            if params:
                runtime_params_str = getAction(params,"name","parameters")
                if runtime_params_str:
                    runtime_params = re.split("[,]?([^,=]+)=", runtime_params_str)[1:]
                    runtime_params = dict(zip(runtime_params[::2], runtime_params[1::2]))
                    doc["runtime_params"] = runtime_params

            totalCount = getAction(actions, "totalCount") or 0
            failCount  = getAction(actions, "failCount") or 0
            skipCount  = getAction(actions, "skipCount") or 0
            doc["claim"] = getClaimReason(actions)
            if totalCount == 0:
                if lastTotalCount == -1:
                    print "Skipping {0} as no test ever passed".format(bid)
                    continue # no tests ever passed for this build
                else:
                    totalCount = lastTotalCount
                    failCount = totalCount
            else:
                lastTotalCount = totalCount

            doc["failCount"] = failCount
            doc["totalCount"] = totalCount - skipCount
            if params is None:
               # possibly new api
               if not 'keys' in dir(actions) and len(actions) > 0:
                   # actions is not a dict and has data
                   # then use the first object that is a list
                   for a in actions:
                      if not 'keys' in dir(a):
                          params = a

            componentParam = getAction(params, "name", "component")
            if componentParam is None:
                testYml = getAction(params, "name", "test")
                if testYml and testYml.find(".yml"):
                    testFile = testYml.split(" ")[1]
                    componentParam = "systest-"+str(os.path.split(testFile)[-1]).replace(".yml","")

            if componentParam:
                subComponentParam = getAction(params, "name", "subcomponent")
                if subComponentParam is None:
                    subComponentParam = "server"
                osParam = getAction(params, "name", "OS") or getAction(params, "name", "os")
                if osParam is None:
                    osParam = doc["os"]
                if not componentParam or not subComponentParam or not osParam:
                    continue

                pseudoName = str(osParam+"-"+componentParam+"_"+subComponentParam)
                doc['subComponent'] = subComponentParam
                doc["name"] = pseudoName
                nameOrig = pseudoName
                _os, _comp = getOsComponent(pseudoName, view)
                if _os and  _comp:
                   doc["os"] = _os
                   doc["component"] = _comp
                if not doc.get("os") or not doc.get("component"):
                   continue


            if bucket == "server-test":
                doc["build"], doc["priority"] = getBuildAndPriority(params)
            else:
                doc["build"], doc["priority"] = getBuildAndPriority(params, True)

            if not doc.get("build"):
                continue

            # run special caveats on collector
            doc["component"] = caveat_swap_xdcr(doc)
            if caveat_should_skip(doc):
                continue

            if caveat_should_skip_mobile(doc):
                continue

            if bucket == "server-test":
               print("Storing for Bid ",bid)
               store_test_cases(doc)
            store_build_details(doc, bucket)

            histKey = doc["name"]+"-"+doc["build"]
            if not first_pass and histKey in buildHist:

                #print "REJECTED- doc already in build results: %s" % doc
                #print buildHist

                # attempt to delete if this record has been stored in couchbase

                try:
                    oldKey = "%s-%s" % (doc["name"], doc["build_id"])
                    oldKey = hashlib.md5(oldKey).hexdigest()
                    purge_job_details(oldKey, bucket)
                    client.remove(oldKey)
                    #print "DELETED- %d:%s" % (bid, histKey)
                except:
                    pass

                continue # already have this build results


            key = "%s-%s" % (doc["name"], doc["build_id"])
            key = hashlib.md5(key).hexdigest()

            try: # get custom claim if exists
                oldDoc = client.get(key)
                customClaim =  oldDoc.value.get('customClaim')
             #  if customClaim is not None:
             #      doc["customClaim"] = customClaim
            except:
                pass #ok, this is new doc

            try:
                client.upsert(key, doc)
                buildHist[histKey] = doc["build_id"]
            except:
                client.upsert(key, doc)
                print "set failed, couchbase down?: %s"  % (HOST)

            if doc.get("claimedBuilds"): # rm custom claim
                  del doc["claimedBuilds"]

    if first_pass:
        storeTest(jobDoc, view, first_pass = False, lastTotalCount = lastTotalCount, claimedBuilds = claimedBuilds)


def storeBuild(client, run, name, view):
    job = getJS(run["url"], {"depth" : 0})
    if not job:
        print "No job info for build"
        return
    result = job.get("result")
    if not result:
        return

    actions = job["actions"]
    totalCount = getAction(actions, "totalCount") or 0
    failCount  = getAction(actions, "failCount") or 0
    skipCount  = getAction(actions, "skipCount") or 0

    if totalCount == 0:
        return

    params = getAction(actions, "parameters")
    os = getAction(params, "name", "DISTRO") or job["fullDisplayName"].split()[2].split(",")[0]
    version = getAction(params, "name", "VERSION")
    build = getAction(params, "name", "CURRENT_BUILD_NUMBER") or getAction(params, "name", "BLD_NUM")

    if not version or not build:
        return

    build = version+"-"+build.zfill(4)

    name=os+"_"+name
    if getAction(params, "name", "UNIT_TEST"):
        name += "_unit"

    os, comp = getOsComponent(name, view)
    if not os or not comp:
        return


    duration = int(job["duration"]) or 0

    # lookup pass count fail count version
    doc = {
      "build_id": int(job["id"]),
      "claim": "",
      "name": name,
      "url": run["url"],
      "component": comp,
      "failCount": failCount,
      "totalCount": totalCount,
      "result": result,
      "duration": duration,
      "priority": "P0",
      "os": os,
      "build": build
    }

    key = "%s-%s" % (doc["name"], doc["build_id"])
    print key+","+build
    key = hashlib.md5(key).hexdigest()

    store_build_details(doc, "build")
    try:
        if version == "4.1.0":
            # not tracking, remove and ignore
            client.remove(key)
        else:
            client.upsert(key, doc)
    except Exception as ex:
        print "set failed, couchbase down?: %s %s"  % (HOST, ex)

def pollBuild(view):

    client = CLIENTS['server'] # using server bucket (for now)

    tJobs = []

    for url in view["urls"]:

        j = getJS(url, {"depth" : 0})
        if j is None:
            continue
        j = j = {
              "_class" : "hudson.model.Hudson",
              "jobs" : [
                  {
                      "_class": "hudson.model.FreeStyleProject",
                      "name": "test_suite_executor",
                      "url": "http://qa.sc.couchbase.com/job/test_suite_executor/",
                      "color": "yellow_anime"
                  }]}
        name = j["name"]
        JOBS[name] = {}
        for job in j["builds"]:
            build_url = job["url"]

            j = getJS(build_url, {"depth" : 0, "tree":"runs[url,number]"})
            if j is None:
                continue

            try:
                if not j:
                    # single run job
                    storeBuild(client, job, name, view)
                else:
                    # each run is a result
                    for doc in j["runs"]:
                        storeBuild(client, doc, name, view)
            except Exception as ex:
                print ex
                pass

def getOsComponent(name, view):
    _os = _comp = None

    PLATFORMS = view["platforms"]
    FEATURES = view["features"]

    for os in PLATFORMS:
        if os in name.upper():
            _os = os

    if _os is None:

        # attempt partial name lookup
        for os in PLATFORMS:
            if os[:3] == name.upper()[:3]:
                _os = os

    if _os is None and view["bucket"] != "mobile":
        # attempt initial name lookup
        for os in PLATFORMS:
            if os[:1] == name.upper()[:1]:
                _os = os

    if _os is None:
       print "%s: job name has unrecognized os: %s" %  (view["bucket"], name)

    for comp in FEATURES:
        tag, _c = comp.split("-")
        docname = name.upper()
        docname = docname.replace("-","_")
        if tag in docname:
            _comp = _c
            break

    if _comp is None:
       print "%s: job name has unrecognized component: %s" %  (view["bucket"], name)

    return _os, _comp

def pollTest(view):

    TEST_CASE_COLLECTOR.pollSubcomponents()

    tJobs = []

    for url in view["urls"]:

        j = getJS(url, {"depth" : 0, "tree" :"jobs[name,url,color]"})
        # j = {"_class":"hudson.model.Hudson","jobs":[{"_class":"hudson.model.FreeStyleProject","name":"test_suite_executor","url":"http://qa.sc.couchbase.com/job/test_suite_executor/","color":"blue"}]}
        if j is None or j.get('jobs') is None:
            continue

        for job in j["jobs"]:
            doc = {}
            doc["name"] = job["name"]
            if job["name"] in JOBS:
                # already processed
                continue

            os, comp = getOsComponent(doc["name"], view)

            if not os or not comp:
                if not isExecutor(job["name"]):
                    # does not match os or comp and is not executor
                    continue
                print(os,comp)
            JOBS[job["name"]] = []
            doc["os"] = os
            doc["component"] = comp
            doc["url"] = job["url"]
            doc["color"] = job.get("color")

            name = doc["name"]
            storeTest(doc,view)
        #     t = Thread(target=storeTest, args=(doc, view))
        #     t.start()
        #     tJobs.append(t)
        #
        #     if len(tJobs) > 10:
        #         # intermediate join
        #         for t in tJobs:
        #             t.join()
        #         tJobs = []
        #
        # for t in tJobs:
        #     t.join()


def convert_changeset_to_old_format(new_doc, timestamp):
    old_format = {}
    old_format['timestamp'] = timestamp
    old_format['changeSet'] = {}
    old_format_items = []
    for change in new_doc['log']:
        item = {}
        msg = change['message']
        # to remove the multiple '\n's, now appearing in the comment
        # that mess with greenboard's display of reviewUrl
        item['msg'] = msg[:msg.index('Change-Id')].replace("\n", " ") +\
                      msg[msg.index('Change-Id') - 1:]
        old_format_items.append(item)
    old_format['changeSet']['items'] = old_format_items
    return old_format


def collectBuildInfo(url):

    client = CLIENTS['server']
    res = getJS(url, {"depth": 1, "tree": "builds[number,url]"})
    if res is None:
        return

    builds = res['builds']
    for b in builds:
        url = b["url"]
        job = getJS(url)
        if job is not None:
            actions = job["actions"]
            params = getAction(actions, "parameters")
            version = getAction(params, "name", "VERSION")
            timestamp = job['timestamp']
            build_no = getAction(params, "name", "BLD_NUM")
            if build_no is None:
                continue
            key = version+"-"+build_no.zfill(4)
            try:
               # check if we have key
               client.get(key)
               continue # already collected changeset
            except:
               pass
            try:
                if version[:3] == "0.0":
                    continue
                if float(version[:3]) > 4.6:
                    changeset_url = CHANGE_LOG_URL+"?ver={0}&from={1}&to={2}".\
                        format(version, str(int(build_no)-1), build_no)
                    job = getJS(changeset_url, append_api_json=False)
                    key = version+"-"+build_no[1:].zfill(4)
                    job = convert_changeset_to_old_format(job, timestamp)
                client.upsert(key, job)
            except:
                print "set failed, couchbase down?: %s"  % (HOST)

def collectAllBuildInfo():
    while True:
       time.sleep(600)
       try:
           for url in BUILDER_URLS:
               collectBuildInfo(url)
       except Exception as ex:
           print "exception occurred during build collection: %s" % (ex)

if __name__ == "__main__":
    createClients()
    # run build collect info thread
    #tBuild = Thread(target=collectAllBuildInfo)
    #tBuild.start()

    #sanitize()
    #get_from_bucket_and_store_build("mobile")
    #get_from_bucket_and_store_build("server")
    TEST_CASE_COLLECTOR.create_client()
    TEST_CASE_COLLECTOR.store_tests()
    print("DONE")
    while True:
        # Poll QE-Test-Suites to retrieve all conf file - subcomponent mappings
        try:
            for view in VIEWS:
                JOBS = {}
                if view["bucket"] == "build":
                    pollBuild(view)
                else:
                    pollTest(view)
            store_existing_jobs()
        except Exception as ex:
            print "exception occurred during job collection: %s" % (ex)
        time.sleep(120)
