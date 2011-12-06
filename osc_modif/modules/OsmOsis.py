#-*- coding: utf-8 -*-

###########################################################################
##                                                                       ##
## Copyrights Etienne Chové <chove@crans.org> 2009                       ##
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

from pyPgSQL import PgSQL, libpq

###########################################################################
## Reader / Writer

class OsmOsis:
    
    def __init__(self, dbstring, schema):
        self._PgConn = PgSQL.Connection(dbstring)
        self._PgCurs = self._PgConn.cursor()
        self._PgCurs.execute("SET search_path TO %s,public;" % schema)
        
    #def __del__(self):
    #    self._PgConn.commit()
        
    def NodeGet(self, NodeId):
        
        self._PgCurs.execute("SELECT nodes.id, st_y(nodes.geom), st_x(nodes.geom), nodes.version, nodes.tstamp, users.name FROM nodes INNER JOIN users ON nodes.user_id = users.id WHERE nodes.id = %d;" % NodeId)
        r1 = self._PgCurs.fetchone()
        if not r1: return None
        data = {}
        data[u"id"]      = r1[0]
        data[u"lat"]     = float(r1[1])
        data[u"lon"]     = float(r1[2])
        data[u"version"] = r1[3]
        data[u"timestamp"] = str(r1[4])
        data[u"user"]    = r1[5].decode("utf8")
        
        data[u"tag"] = {}
        self._PgCurs.execute("SELECT (each(tags)).key, (each(tags)).value FROM nodes WHERE id = %d;" % NodeId)
        for r1 in self._PgCurs.fetchall():
            data[u"tag"][r1[0].decode("utf8")] = r1[1].decode("utf8")
            
        return data
    
    def WayGet(self, WayId):
        
        self._PgCurs.execute("SELECT ways.id, ways.version, ways.tstamp, users.name FROM ways INNER JOIN users ON ways.user_id = users.id WHERE ways.id = %d;" % WayId)
        r1 = self._PgCurs.fetchone()
        if not r1: return None
        data = {}
        data[u"id"]      = r1[0]
        data[u"version"] = r1[1]
        data[u"timestamp"] = str(r1[2])
        data[u"user"]    = r1[3].decode("utf8")
        
        data[u"tag"] = {}
        self._PgCurs.execute("SELECT (each(tags)).key, (each(tags)).value FROM ways WHERE id = %d;" % WayId)
        for r1 in self._PgCurs.fetchall():
            data[u"tag"][r1[0].decode("utf8")] = r1[1].decode("utf8")
        
        data[u"nd"] = []
        self._PgCurs.execute("SELECT node_id FROM way_nodes WHERE way_id = %d ORDER BY sequence_id;" % WayId)
        for r1 in self._PgCurs.fetchall():
            data[u"nd"].append(r1[0])
            
        return data

    def RelationGet(self, RelationId):
        
        self._PgCurs.execute("SELECT relations.id, relations.version, relations.tstamp, users.name FROM relations INNER JOIN users ON relations.user_id = users.id WHERE relations.id = %d;" % RelationId)
        r1 = self._PgCurs.fetchone()
        if not r1: return None
        data = {}
        data[u"id"]      = r1[0]
        data[u"version"] = r1[1]
        data[u"timestamp"] = str(r1[2])
        data[u"user"]    = r1[3].decode("utf8")
        
        data[u"tag"] = {}
        self._PgCurs.execute("SELECT (each(tags)).key, (each(tags)).value FROM relations WHERE id = %d;" % RelationId)
        for r1 in self._PgCurs.fetchall():
            data[u"tag"][r1[0].decode("utf8")] = r1[1].decode("utf8")
        
        data[u"member"] = []
        self._PgCurs.execute("SELECT member_id, member_type, member_role FROM relation_members WHERE relation_id = %d ORDER BY sequence_id;" % RelationId)
        for r1 in self._PgCurs.fetchall():
            data[u"member"].append({u"ref":r1[0], u"type":{"N":"node","W":"way","R":"relation"}[r1[1]], u"role":r1[2].decode("utf8")})
            
        return data

    def NodeGetPosition(self, NodeId):
        
        self._PgCurs.execute("SELECT nodes.id, st_y(nodes.geom), st_x(nodes.geom), nodes.version, nodes.tstamp FROM nodes WHERE nodes.id = %d;" % NodeId)
        r1 = self._PgCurs.fetchone()
        if not r1: return None
        data = {}
        data[u"id"]  = r1[0]
        data[u"lat"] = float(r1[1])
        data[u"lon"] = float(r1[2])
        data[u"version"]   = r1[3]
        data[u"timestamp"] = str(r1[4])
        data[u"tag"] = {}
            
        return data

    def WayGetNodes(self, WayId):
        
        self._PgCurs.execute("SELECT ways.id FROM ways WHERE ways.id = %d;" % WayId)
        r1 = self._PgCurs.fetchone()
        if not r1: return None
        data = {}
        data[u"id"]  = r1[0]
        data[u"tag"] = {}
        data[u"nd"]  = []
        self._PgCurs.execute("SELECT node_id FROM way_nodes WHERE way_id = %d ORDER BY sequence_id;" % WayId)
        for r1 in self._PgCurs.fetchall():
            data[u"nd"].append(r1[0])
            
        return data

    def RelationGetMembers(self, RelationId):
        
        self._PgCurs.execute("SELECT relations.id FROM relations WHERE relations.id = %d;" % RelationId)
        r1 = self._PgCurs.fetchone()
        if not r1: return None
        data = {}
        data[u"id"]  = r1[0]
        data[u"tag"] = {}
        data[u"member"] = []
        self._PgCurs.execute("SELECT member_id, member_type, member_role FROM relation_members WHERE relation_id = %d ORDER BY sequence_id;" % RelationId)
        for r1 in self._PgCurs.fetchall():
            data[u"member"].append({u"ref":r1[0], u"type":{"N":"node","W":"way","R":"relation"}[r1[1]], u"role":r1[2].decode("utf8")})
            
        return data

    def NodeExists(self, NodeId):
        
        self._PgCurs.execute("SELECT nodes.id FROM nodes WHERE nodes.id = %d;" % NodeId)
        r1 = self._PgCurs.fetchone()
        if not r1:
            return None
        return True

    def WayExists(self, WayId):
        
        self._PgCurs.execute("SELECT ways.id FROM ways WHERE ways.id = %d;" % WayId)
        r1 = self._PgCurs.fetchone()
        if not r1:
            return None
        return True

    def RelationExists(self, RelationId):
        
        self._PgCurs.execute("SELECT relations.id FROM relations WHERE relations.id = %d;" % RelationId)
        r1 = self._PgCurs.fetchone()
        if not r1:
            return None
        return True
