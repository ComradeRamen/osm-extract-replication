#!/usr/bin/env python
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

import os, urllib, lockfile, shutil, time, dateutil.parser, dateutil.tz
import multiprocessing
import sys
import osc_modif
from modules import OsmBin
from modules import OsmSax

# configuration
skip_diff_generation = False
multiproc_enabled = True
work_path = "/data/work/osmbin/replication"
work_diffs_path = os.path.join(work_path, "diffs")
type_replicate = "minute"
#type_replicate = "day-replicate"
orig_diff_path = os.path.join(work_diffs_path, "planet", type_replicate)
bbox_diff_path = os.path.join(work_diffs_path, "bbox", type_replicate)
modif_diff_path = []
poly_file = []

os.chdir("polygons")
for (r,d,files) in os.walk("."):
  for f in files:
     if f.endswith(".poly"):
        poly_file.append(os.path.join(r, f))
        p = os.path.join(r, f[:-len(".poly")])
        modif_diff_path.append(os.path.join(work_diffs_path, p, type_replicate))

remote_diff_url = "http://planet.openstreetmap.org/replication/" + type_replicate
lock_file = os.path.join(work_path, "update.lock")

###########################################################################

def update_hardlink(src, dst):
  if os.path.exists(dst):
    os.remove(dst)
  os.link(src, dst)

def update_symlink(src, dst):
  if os.path.exists(dst) and not os.path.islink(dst):
    raise Exception, "File '%s' is not a symbolic link" % dst
  if os.path.exists(dst):
    os.remove(dst)
  os.symlink(src, dst)

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
  print time.strftime("%H:%M:%S"), "  generate bbox"
  sys.stdout.flush()
  osc_modif.osc_modif(None, osc_modif_options)
  os.rename(modif_diff_file + "-tmp.osc.gz", modif_diff_file + ".osc.gz")
  os.utime(modif_diff_file + ".osc.gz", (file_date, file_date))
  update_hardlink(orig_diff_file + ".state.txt", modif_diff_file + ".state.txt")

  # update symbolic link to state.txt
  modif_state_file = os.path.join(modif_diff_path, "state.txt")
  update_symlink(modif_diff_file + ".state.txt", modif_state_file)
  os.utime(modif_state_file, (file_date, file_date))
  print time.strftime("%H:%M:%S"), "  finish bbox"
  sys.stdout.flush()


def generate_diff(orig_diff_path, file_location, file_date, modif_poly, modif_diff_path):

  orig_diff_file = os.path.join(orig_diff_path, file_location)
  modif_diff_file = os.path.join(modif_diff_path, file_location)

  class osc_modif_options:
    source = orig_diff_file + ".osc.gz"
    dest = modif_diff_file + "-tmp.osc.gz"
    poly = modif_poly
    position_only = False

  # apply polygon
  print time.strftime("%H:%M:%S"), "  apply polygon", modif_poly
  sys.stdout.flush()
  osc_modif.osc_modif(None, osc_modif_options)
  os.rename(modif_diff_file + "-tmp.osc.gz", modif_diff_file + ".osc.gz")
  os.utime(modif_diff_file + ".osc.gz", (file_date, file_date))
  update_hardlink(orig_diff_file + ".state.txt", modif_diff_file + ".state.txt")

  # update symbolic link to state.txt
  modif_state_file = os.path.join(modif_diff_path, "state.txt")
  update_symlink(modif_diff_file + ".state.txt", modif_state_file)
  os.utime(modif_state_file, (file_date, file_date))
#  print time.strftime("%H:%M:%S"), "  finish polygon", modif_poly
  sys.stdout.flush()

###########################################################################

def update():
  # get lock
  if not os.path.exists(work_path):
    os.makedirs(work_path)
  lock = lockfile.FileLock(lock_file)
  lock.acquire(timeout=0)

  # get local sequence number
  def get_sequence_num(f):
    for line in f:
      (key, sep, value) = line.partition("=")
      if key.strip() == "sequenceNumber":
        return int(value)

  try:
    print os.path.join(orig_diff_path, "state.txt")
    f = open(os.path.join(orig_diff_path, "state.txt"), "r")
    begin_sequence = get_sequence_num(f)
    f.close()
  except IOError:
    begin_sequence = 0

  # get remote sequence number
  try:
    f = urllib.urlopen(os.path.join(remote_diff_url, "state.txt"), "r")
  except IOError:
    lock.release()
    raise
  end_sequence = min(begin_sequence + 10000, get_sequence_num(f))
  f.close()

  try:
    begin_sequence = int(begin_sequence)
    end_sequence = int(end_sequence)
  except TypeError:
    lock.release()
    raise

  # download diffs, and apply the polygon on them
  for i in xrange(begin_sequence + 1, end_sequence + 1):
    print time.strftime("%H:%M:%S"), i
    for path in [orig_diff_path] + modif_diff_path + [bbox_diff_path]:
      tmp_path = os.path.join(path, "%03d/%03d" % (i // (1000 * 1000), (i // 1000) % 1000))
      if not os.path.exists(tmp_path):
        os.makedirs(tmp_path)

    file_location = "%03d/%03d/%03d" % (i // (1000 * 1000), (i // 1000) % 1000, i % 1000)

    # download diff file
    print time.strftime("%H:%M:%S"), "  download diff"
    orig_diff_file = os.path.join(orig_diff_path, file_location)
    for ext in (".osc.gz", ".state.txt"):
      try:
        (filename, headers) = urllib.urlretrieve(os.path.join(remote_diff_url, file_location) + ext, orig_diff_file + ext)
      except IOError:
        lock.release()
        raise
      file_date = time.mktime(dateutil.parser.parse(headers["Last-Modified"]).astimezone(dateutil.tz.tzlocal()).timetuple())
      os.utime(orig_diff_file + ext, (file_date, file_date))

    if not skip_diff_generation:
      generate_bbox_diff(orig_diff_path, file_location, file_date, bbox_diff_path)

      pool = multiprocessing.Pool(processes=8)
      res = []

      for i in xrange(len(modif_diff_path)):
        if multiproc_enabled:
          res.append(pool.apply_async(generate_diff,
                                      (bbox_diff_path, file_location, file_date,
                                       poly_file[i], modif_diff_path[i])))
        else:
          generate_diff(bbox_diff_path, file_location, file_date,
                        poly_file[i], modif_diff_path[i])

      if multiproc_enabled:
        for r in res:
          r.get()

      pool.close()
      pool.join()

    # update osmbin
    print time.strftime("%H:%M:%S"), "  update osmbin"
    diff_read = OsmSax.OscSaxReader(orig_diff_file + ".osc.gz")
    o = OsmBin.OsmBin("/data/work/osmbin/data", "w")
    diff_read.CopyTo(o)
    del o
    del diff_read

    # update symbolic links to state.txt
    print time.strftime("%H:%M:%S"), "  update links to state.txt"
    update_symlink(orig_diff_file + ".state.txt", os.path.join(orig_diff_path, "state.txt"))
    os.utime(os.path.join(orig_diff_path, "state.txt"), (file_date, file_date))
    sys.stdout.flush()

  # free lock
  sys.stdout.flush()
  lock.release()

if __name__ == '__main__':
  update()
