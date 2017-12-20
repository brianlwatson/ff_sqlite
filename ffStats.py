import re
import sqlite3
import sys
import time
import operator
import ffScraper


# Calculations
class TeamProjComposition:
	def __init__(self):
		self.owner = 0
		self.week = 0
		self.pts = 0.0

		self.qbs = {}
		self.backs = {}
		self.receivers = {}
		self.tightEnds = {}
		self.flexes = {}
		self.dst = {}
		self.kickers = {}

		self.bestQB = ("", 0.0)
		self.bestRB1 = ("", 0.0)
		self.bestRB2 = ("", 0.0)
		self.bestWR1 = ("", 0.0)
		self.bestWR2 = ("", 0.0)
		self.bestTE = ("", 0.0)
		self.bestFLX1 = ("", 0.0)
		self.bestFLX2 = ("", 0.0)
		self.bestDST = ("", 0.0)
		self.bestKick = ("", 0.0)

	def addToTeam(self, player):
		if player.position == "QB":
			self.qbs[player.name] = player.projPoints
		elif player.position == "RB":
			self.backs[player.name] = player.projPoints
		elif player.position == "WR":
			self.receivers[player.name] = player.projPoints
		elif player.position == "TE":
			self.tightEnds[player.name] = player.projPoints
		elif player.position == "D/ST":
			self.dst[player.name] = player.projPoints
		else:
			self.kickers[player.name] = player.projPoints

	def composeBestProjTeam(self):
		for name, projScore in self.qbs.items():
			if projScore == "--":
				projScore = 0.0
			if projScore > self.bestQB[1]:
				self.bestQB = (name, projScore)
		for name, projScore in self.backs.items():
			if projScore == "--":
				projScore = 0.0
			if projScore > self.bestRB1[1]:
				self.bestRB2 = self.bestRB1
				self.bestRB1 = (name, projScore)
			elif projScore > self.bestRB2[1]:
				self.bestRB2 = (name, projScore)
		for name, projScore in self.receivers.items():
			if projScore == "--":
				projScore = 0.0
			if projScore > self.bestWR1[1]:
				self.bestWR2 = self.bestWR1
				self.bestWR1 = (name, projScore)
			elif projScore > self.bestWR2[1]:
				self.bestWR2 = (name, projScore)
		for name, projScore in self.tightEnds.items():
			if projScore == "--":
				projScore = 0.0
			if projScore > self.bestTE[1]:
				self.bestTE = (name, projScore)
		possFlexes = dict(self.backs)
		possFlexes.update(self.receivers)
		possFlexes.update(self.tightEnds)
		del possFlexes[self.bestRB1[0]]
		del possFlexes[self.bestRB2[0]]
		del possFlexes[self.bestWR1[0]]
		del possFlexes[self.bestWR2[0]]
		del possFlexes[self.bestTE[0]]
		possFlexes = sorted(possFlexes.items(), key=operator.itemgetter(1))
		self.bestFLX1 = possFlexes[-1]
		self.bestFLX2 = possFlexes[-2]
		for name, projScore in self.dst.items():
			if projScore == "--":
				projScore = 0.0
			if projScore > self.bestDST[1]:
				self.bestDST = (name, projScore)
		for name, projScore in self.kickers.items():
			if projScore == "--":
				projScore = 0.0
			if projScore > self.bestKick[1]:
				self.bestKick = (name, projScore)

	def printBestProjTeam(self):
		print "Owner: "+str(self.owner)+", week "+str(self.week)
		print "Using projections, the best lineup (based on owned players) is:"
		print "QB: "+str(self.bestQB[0])+", "+str(self.bestQB[1])
		print "RB1: "+str(self.bestRB1[0])+", "+str(self.bestRB1[1])
		print "RB2: "+str(self.bestRB2[0])+", "+str(self.bestRB2[1])
		print "WR1: "+str(self.bestWR1[0])+", "+str(self.bestWR1[1])
		print "WR2: "+str(self.bestWR2[0])+", "+str(self.bestWR2[1])
		print "TE: "+str(self.bestTE[0])+", "+str(self.bestTE[1])
		print "FLX1: "+str(self.bestFLX1[0])+", "+str(self.bestFLX1[1])
		print "FLX2: "+str(self.bestFLX2[0])+", "+str(self.bestFLX2[1])
		print "D/ST: "+str(self.bestDST[0])+", "+str(self.bestDST[1])
		print "Kicker: "+str(self.bestKick[0])+", "+str(self.bestKick[1])
		self.pts = float(self.bestQB[1])+float(self.bestRB1[1])+float(self.bestRB2[1])+float(self.bestWR1[1])+float(self.bestWR2[1])+float(self.bestTE[1])+float(self.bestDST[1])+float(self.bestKick[1])
		print "Proj Team Points: " + str(self.pts)
		print

	def printTeam(self):
		print "QUARTERBACKS:"
		for name, projScore in self.qbs.items():
			print name + ", " + str(projScore)
		print "RUNNINGBACKS:"
		for name, projScore in self.backs.items():
			print name + ", " + str(projScore)
		print "RECEIVERS:"
		for name, projScore in self.receivers.items():
			print name + ", " + str(projScore)
		print "TIGHTENDS:"
		for name, projScore in self.tightEnds.items():
			print name + ", " + str(projScore)
		print "D/ST:"
		for name, projScore in self.dst.items():
			print name + ", " + str(projScore)
		print "KICKERS:"
		for name, projScore in self.kickers.items():
			print name + ", " + str(projScore)

def getBestProjLineup(ownerId):
	db = sqlite3.connect(ffScraper.LEAGUE_ID.split("=")[-1]+".sqlite")
	c=db.cursor()
	result = []
	# for ownerId in range(1,len(fantasyOwners)+1):
	for week in range(1,ffScraper.REG_SEASON_WEEKS+1):
		c.execute("SELECT * FROM projections WHERE owner=:owner AND week=:week", {"owner": ownerId, "week": float(week)})
		result.append(c.fetchall())
	db.close()
	projTeams = []
	for team in result:
		projTeam = TeamProjComposition()
		for player in team:
			name=player[0]
			nflTeam=player[1]
			pos=player[2]
			proj=player[3]
			owner=player[4]
			week=player[5]
			pp = ffScraper.PlayerProjection(name,nflTeam,pos,proj,owner,week)
			projTeam.owner = owner
			projTeam.week = week
			projTeam.addToTeam(pp)
		projTeams.append(projTeam)
	for team in projTeams:
		team.composeBestProjTeam()
		team.printBestProjTeam()


