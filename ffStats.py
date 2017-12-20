import re
import sqlite3
import sys
import time
import operator
import ffScraper


#These two classes will be used for printing out to html
class FantasyStatRow:
	def __init__(self):
		self.name=""
		self.stats=[]
	def printRow(self):
		print self.name,"\t",self.stats

class FantasyStatTable:
	def __init__(self):
		self.description=""
		self.tableHeaders=[]
		self.rows=[] #List of FantasyStatRows
	def printTable(self):
		print self.description
		print "Team Name\t", self.tableHeaders
		for tr in self.rows:
			print tr.name,"\t",tr.stats
		print "\n"
	def getHtmlTable(self, tableName):
		tableString="\n\n<h1>"+self.description+"</h1>\n"
		tableString=tableString+"<table id="+tableName+">\n"
		tableHeaders="  <tr>\n"
		tableHeaders=tableHeaders+"    <th>Team Name</th>\n"
		for th in self.tableHeaders:
			tableHeaders=tableHeaders+"    <th>"+th+"</th>\n"
		tableHeaders=tableHeaders+"  </tr>\n"
		tableString=tableString+tableHeaders

		for td in self.rows:
			tempRow="  <tr>\n"
			tempRow=tempRow+"    <td>"+td.name+"</td>\n"
			for stat in td.stats:
				tempRow=tempRow+"    <td>"+stat+"</td>\n"
			tempRow=tempRow+"  </tr>\n"
			tableString=tableString+tempRow


		tableString=tableString+"</table>\n"
		return tableString

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

def getGamesForAgainst(ownerId, pointThreshold):
	db = sqlite3.connect(ffScraper.LEAGUE_ID.split("=")[-1]+".sqlite")
	c=db.cursor()
	gamesAgainst=[]
	gamesFor=[]
	numGamesFor=0
	numGamesAgainst=0

	fRow=FantasyStatRow()
	fRow.name = ffScraper.fantasyOwners[ownerId-1].teamName

	#Calculate games for where started players have scored greater than or equal to threshold
	c.execute("SELECT * FROM scores WHERE owner={owner} AND started={started} AND points>={points}".\
		format(points=pointThreshold, owner=ownerId, started=1))
	#c.execute("SELECT * FROM scores WHERE owner=:owner AND points>:points AND started=:started", {"owner": ownerId, "points": pointThreshold, "started": 1})
	gamesFor.append(c.fetchall())

	#Query for games in which ownerID's opponent started a player that met or surpassed the threshold
	for week in range(1, ffScraper.REG_SEASON_WEEKS+1):
		oppID=ffScraper.fantasyOwners[ownerId-1].opponentIDs[week-1]
		c.execute("SELECT * FROM scores WHERE owner={owner} AND started={started} AND points>={points} AND week={week}".\
			format(points=pointThreshold, owner=oppID, started=1, week=week))
		gamesAgainst.append(c.fetchall())

	#If debug is needed, the contents of gamesFor and gamesAgainst will display the query results

	numGamesFor=sum([len(g) for g in gamesFor])
	fRow.stats.append(str(numGamesFor))
	numGamesAgainst=sum([len(g) for g in gamesAgainst])
	fRow.stats.append(str(numGamesAgainst))

	return fRow








