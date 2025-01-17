#!/usr/bin/env python3
#-*- coding: utf-8 -*-

###########################################################################
##                                                                       ##
## Copyrights Jocelyn Jaubert                 2011                       ##
##                                                                       ##
## This program is free software: you can redistribute it and/or modify  ##
## it under the terms of the GNU General Public License as published by  ##
## the Free Software Foundation, either version 3 of the License, or     ##
## (at your option) any later version.                                   ##
##                                                                       ##
## This program is distributed in the hope that it will be useful,       ##
## but WITHOUT ANY WARRANTY; without even the implied warranty of        ##
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         ##
## GNU General Public License for more details.                          ##
##                                                                       ##
## You should have received a copy of the GNU General Public License     ##
## along with this program.  If not, see <http://www.gnu.org/licenses/>. ##
##                                                                       ##
###########################################################################

import os, fasteners, shutil, time, dateutil.parser, dateutil.tz
import multiprocessing
import urllib.request
import sys
import osc_modif
from modules import OsmBin
from modules import OsmSax

# configuration
work_path = "/data/work/osmbin/replication"
work_diffs_path = os.path.join(work_path, "diffs")
type_replicate = "minute"
#type_replicate = "day-replicate"
orig_diff_path = os.path.join(work_diffs_path, "planet", type_replicate)
bbox_diff_path = os.path.join(work_diffs_path, "bbox", type_replicate)

countries_param = {}
modif_diff_path = []
dependencies = {}

os.chdir("polygons")
for (r,d,files) in os.walk("."):
  for f in files:
     if f.endswith(".poly"):
        country_poly = os.path.join(r, f)
        p = os.path.join(r, f[:-len(".poly")])
        dependencies[p] = []
        for i in range(1, p.count("/")):
            father = "/".join(p.split("/")[:-i])
            if father in dependencies:
                dependencies[father] += [p]
                break
        country_diff = os.path.join(work_diffs_path, p, type_replicate)
        modif_diff_path.append(country_diff)
        countries_param[p] = (country_poly, country_diff)

# Find countries without any dependencies
orig_top_countries = dependencies.keys()
top_countries = list(orig_top_countries)
for (k,v) in dependencies.items():
  for c in v:
    if c in orig_top_countries:
      top_countries.remove(c)

remote_diff_url = "https://planet.openstreetmap.org/replication/" + type_replicate
lock_file = os.path.join(work_path, "update.lock")

###########################################################################

def update_hardlink(src, dst):
  if os.path.exists(dst):
    os.remove(dst)
  os.link(src, dst)

def update_symlink(src, dst):
  if os.path.exists(dst) and not os.path.islink(dst):
    raise Exception( "File '%s' is not a symbolic link" % dst)
  if os.path.exists(dst):
    os.remove(dst)
  try:
    os.symlink(src, dst)
  except:
    print("FAIL on update_symlink(%s, %s)" % (src, dst))
    raise

def generate_bbox_diff(orig_diff_path, file_location, file_date, modif_diff_path):

  orig_diff_file = os.path.join(orig_diff_path, file_location)
  modif_diff_file = os.path.join(modif_diff_path, file_location)

  class osc_modif_options:
    source = orig_diff_file + ".osc.gz"
    dest = modif_diff_file + "-tmp.osc.gz"
    poly = False
    bbox = True
    position_only = False

  # apply polygon
  print(time.strftime("%Y-%m-%d %H:%M:%S"), "  generate bbox")
  sys.stdout.flush()
  osc_modif.osc_modif(None, osc_modif_options)
  os.rename(modif_diff_file + "-tmp.osc.gz", modif_diff_file + ".osc.gz")
  os.utime(modif_diff_file + ".osc.gz", (file_date, file_date))
  update_hardlink(orig_diff_file + ".state.txt", modif_diff_file + ".state.txt")

  # update symbolic link to state.txt
  modif_state_file = os.path.join(modif_diff_path, "state.txt")
  update_symlink(modif_diff_file + ".state.txt", modif_state_file)
  os.utime(modif_state_file, (file_date, file_date))
  print(time.strftime("%Y-%m-%d %H:%M:%S"), "  finish bbox")
  sys.stdout.flush()


def generate_diff(orig_diff_path, file_location, file_date, modif_poly, modif_diff_path, country):

  orig_diff_file = os.path.join(orig_diff_path, file_location)
  modif_diff_file = os.path.join(modif_diff_path, file_location)

  class osc_modif_options:
    source = orig_diff_file + ".osc.gz"
    dest = modif_diff_file + "-tmp.osc.gz"
    poly = modif_poly
    position_only = False

  # apply polygon
  print(time.strftime("%Y-%m-%d %H:%M:%S"), "  apply polygon", modif_poly)
  sys.stdout.flush()
  osc_modif.osc_modif(None, osc_modif_options)
  os.rename(modif_diff_file + "-tmp.osc.gz", modif_diff_file + ".osc.gz")
  os.utime(modif_diff_file + ".osc.gz", (file_date, file_date))
  update_hardlink(orig_diff_file + ".state.txt", modif_diff_file + ".state.txt")

  # update symbolic link to state.txt
  modif_state_file = os.path.join(modif_diff_path, "state.txt")
  update_symlink(modif_diff_file + ".state.txt", modif_state_file)
  os.utime(modif_state_file, (file_date, file_date))
  print(time.strftime("%Y-%m-%d %H:%M:%S"), "  finish polygon", modif_poly)
  sys.stdout.flush()

  return (country, file_location, file_date)

###########################################################################

def launch_dep_countries(res):

  global multiproc_enabled
  global pool
  global pool_jobs
  global lock_num_launched
  global num_launched

  if multiproc_enabled:
    lock_num_launched.acquire()

  for c in dependencies[res[0]]:
    country_param = countries_param[c]
    num_launched += 1
    if multiproc_enabled:
      pool_jobs.append(pool.apply_async(generate_diff,
                                        (countries_param[res[0]][1], res[1], res[2],
                                         country_param[0], country_param[1], c),
                                        callback=launch_dep_countries))
    else:
      new_res = generate_diff(countries_param[res[0]][1], res[1], res[2],
                              country_param[0], country_param[1], c)
      launch_dep_countries(new_res)

  num_launched -= 1
  if multiproc_enabled:
    lock_num_launched.release()


###########################################################################

def update(wanted_end_sequence=None):

  global pool
  global pool_jobs
  global lock_num_launched
  global num_launched

  # get lock
  if not os.path.exists(work_path):
    os.makedirs(work_path)
  lock = fasteners.InterProcessLock(lock_file)
  gotten = lock.acquire(timeout=5)
  if not gotten:
    raise Exception("Couldn't take lock: " + lock_file)

  # get local sequence number
  def get_sequence_num(s):
    for line in s.split("\n"):
      (key, sep, value) = line.partition("=")
      if key.strip() == "sequenceNumber":
        return int(value)

  try:
    print(os.path.join(orig_diff_path, "state.txt"))
    f = open(os.path.join(orig_diff_path, "state.txt"), "r")
    begin_sequence = get_sequence_num(f.read())
    f.close()
  except IOError:
    lock.release()
    raise

  # get remote sequence number
  try:
    f = urllib.request.urlopen(os.path.join(remote_diff_url, "state.txt"))
    server_state = f.read().decode("utf-8")
  except IOError:
    lock.release()
    raise
  end_sequence = min(begin_sequence + 10000, get_sequence_num(server_state))
  if wanted_end_sequence:
    end_sequence = min(end_sequence, wanted_end_sequence)
  f.close()

  try:
    begin_sequence = int(begin_sequence)
    end_sequence = int(end_sequence)
  except TypeError:
    lock.release()
    raise

  # download diffs, and apply the polygon on them
  for i in range(begin_sequence + 1, end_sequence + 1):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), i)
    for path in [orig_diff_path] + modif_diff_path + [bbox_diff_path]:
      tmp_path = os.path.join(path, "%03d/%03d" % (i // (1000 * 1000), (i // 1000) % 1000))
      if not os.path.exists(tmp_path):
        os.makedirs(tmp_path)

    file_location = "%03d/%03d/%03d" % (i // (1000 * 1000), (i // 1000) % 1000, i % 1000)

    # download diff file
    print(time.strftime("%Y-%m-%d %H:%M:%S"), "  download diff")
    orig_diff_file = os.path.join(orig_diff_path, file_location)
    for ext in (".osc.gz", ".state.txt"):
      try:
        (filename, headers) = urllib.request.urlretrieve(os.path.join(remote_diff_url, file_location) + ext, orig_diff_file + ext)
      except IOError:
        lock.release()
        raise
      file_date = time.mktime(dateutil.parser.parse(headers["Last-Modified"]).astimezone(dateutil.tz.tzlocal()).timetuple())
      os.utime(orig_diff_file + ext, (file_date, file_date))

    if not skip_diff_generation:
      generate_bbox_diff(orig_diff_path, file_location, file_date, bbox_diff_path)

      if multiproc_enabled:
        lock_num_launched.acquire()

      for country in top_countries:
        country_param = countries_param[country]
        num_launched += 1
        if multiproc_enabled:
          pool_jobs.append(pool.apply_async(generate_diff,
                                            (bbox_diff_path, file_location, file_date,
                                             country_param[0], country_param[1], country),
                                            callback=launch_dep_countries))
        else:
          pool_jobs = generate_diff(bbox_diff_path, file_location, file_date,
                                    country_param[0], country_param[1], country)
          launch_dep_countries(pool_jobs)

      if multiproc_enabled:
        lock_num_launched.release()
        while True:
          lock_num_launched.acquire()
          local_num_launched = num_launched
          lock_num_launched.release()
          if local_num_launched == 0 and len(pool_jobs) == 0:
            break
          for r in pool_jobs:
            r.get()
            pool_jobs.remove(r)

      assert num_launched == 0

    # update osmbin
    print(time.strftime("%Y-%m-%d %H:%M:%S"), "  update osmbin")
    diff_read = OsmSax.OscSaxReader(orig_diff_file + ".osc.gz")
    o = OsmBin.OsmBin("/data/work/osmbin/data", "w")
    diff_read.CopyTo(o)
    del o
    del diff_read

    # update symbolic links to state.txt
    print(time.strftime("%Y-%m-%d %H:%M:%S"), "  update links to state.txt")
    update_symlink(orig_diff_file + ".state.txt", os.path.join(orig_diff_path, "state.txt"))
    os.utime(os.path.join(orig_diff_path, "state.txt"), (file_date, file_date))
    sys.stdout.flush()

  if multiproc_enabled:
    pool.close()
    pool.join()

  # free lock
  sys.stdout.flush()
  lock.release()

if __name__ == '__main__':
  from optparse import OptionParser

  parser = OptionParser()
  parser.add_option("--list", action="store_true",
                    help="List countries")
  parser.add_option("--end", action="store",
                    help="Stop generation at number <END> instead of latest from server")
  parser.add_option("--no-multiproc", dest="multiproc", action="store_false", default=True,
                    help="Disable running multiple processes in parallel")
  parser.add_option("--skip-diff-generation", dest="skip_diff_generation", action="store_true",
                    help="Only update database, without generating diffs")
  (options, args) = parser.parse_args()


  if options.list:
    import pprint
    pprint.pprint(sorted(top_countries))
    pprint.pprint(dependencies)
    sys.exit(0)

  if options.end:
    wanted_end_sequence = int(options.end)
  else:
    wanted_end_sequence = None

  multiproc_enabled = options.multiproc
  skip_diff_generation = options.skip_diff_generation

  if multiproc_enabled:
    pool = multiprocessing.Pool(processes=8)
  lock_num_launched = multiprocessing.Lock()
  num_launched = 0
  pool_jobs = []

  update(wanted_end_sequence)
