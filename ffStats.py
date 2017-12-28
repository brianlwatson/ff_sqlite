import re
import sqlite3
import sys
import time
import operator
import ffScraper
from operator import itemgetter
class FantasyPlayer:
	def __init__(self):
		self.name=""
		self.nflTeam=""
		self.position=""
		self.owner=0
		self.week=0
		self.started=0
		self.score=0
		self.projection=0
		self.miscStats=[] #This can serve as anything
		self.miscInt=0
	def printPlayer(self):
		print (self.name, self.position, self.nflTeam, "ownerID="+str(self.owner), "week="+str(self.week), "started="+str(self.started), "projection="+str(self.projection),
		 	"score="+str(self.score),"miscInt="+str(self.miscInt),"\n")
	def scoreQueryToPlayer(self, query):
		#Based on the format of a SELECT * from scores table
		self.name=query[0]
		self.nflTeam=query[1]
		self.position=query[2]
		self.projection=(query[3])
		self.score=(query[4])
		self.started=(query[5])
		self.owner=(query[6])
		self.week=(query[7])

def intToPlusMinusHTML(value):
	if value >= 0.0:
		return str("<span class=\"posValue\">+"+str(value)+"</span>")
	else:
		return str("<span class=\"negValue\">"+str(value)+"</span>")

def addHTMLClass(value, spanClass):
	return str("<span class=\""+spanClass+"\">"+value+"</span>")

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
		tableHeaders=tableHeaders+"    <th>Name</th>\n"
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
	db = sqlite3.connect(ffScraper.DB_NAME)
	c=db.cursor()
	result = []
	# for ownerId in range(1,len(fantasyOwners)+1):
	for week in range(1,ffScraper.REG_SEASON_WEEKS+1):
		c.execute("SELECT * FROM scores WHERE owner=:owner AND week=:week", {"owner": ownerId, "week": float(week)})
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
			score=0.0
			started=0
			pp = ffScraper.PlayerScores(name,nflTeam,pos,proj,score,started,owner,week)
			projTeam.owner = owner
			projTeam.week = week
			projTeam.addToTeam(pp)
		projTeams.append(projTeam)
	for team in projTeams:
		team.composeBestProjTeam()
		team.printBestProjTeam()

def getGamesForAgainst(ownerId, pointThreshold):
	db = sqlite3.connect(ffScraper.DB_NAME)
	c=db.cursor()
	gamesAgainst=[]
	gamesFor=[]
	numGamesFor=0
	numGamesAgainst=0

	fRow=FantasyStatRow()
	fRow.name = ffScraper.fantasyOwners[ownerId-1].teamName

	#Calculate games for where started players have scored greater than or equal to threshold
	c.execute("SELECT * FROM scores WHERE owner={owner} AND started={started} AND score>={points}".\
		format(points=pointThreshold, owner=ownerId, started=1))
	#c.execute("SELECT * FROM scores WHERE owner=:owner AND points>:points AND started=:started", {"owner": ownerId, "points": pointThreshold, "started": 1})
	gamesFor.append(c.fetchall())

	#Query for games in which ownerID's opponent started a player that met or surpassed the threshold
	for week in range(1, ffScraper.REG_SEASON_WEEKS+1):
		oppID=ffScraper.fantasyOwners[ownerId-1].opponentIDs[week-1]
		c.execute("SELECT * FROM scores WHERE owner={owner} AND started={started} AND score>={points} AND week={week}".\
			format(points=pointThreshold, owner=oppID, started=1, week=week))
		gamesAgainst.append(c.fetchall())

	#If debug is needed, the contents of gamesFor and gamesAgainst will display the query results

	numGamesFor=sum([len(g) for g in gamesFor])
	fRow.stats.append(str(numGamesFor))
	numGamesAgainst=sum([len(g) for g in gamesAgainst])
	fRow.stats.append(str(numGamesAgainst))

	return fRow

#Calculate 
def calcProjectionAccuracy(ownerId, verbosity):
	db = sqlite3.connect(ffScraper.DB_NAME)
	c=db.cursor()

	tables=[]

	totalTable=FantasyStatTable()
	totalTable.description=str("Total ESPN Projection +/- for "+ffScraper.leagueMembers[ownerId-1])
	totalTable.tableHeaders=["Score","Projection","+/-"]

	seasonPlusMinus=0
	seasonScored=0
	seasonProjected=0

	for week in range(1,ffScraper.REG_SEASON_WEEKS+1):
		started=[]
		c.execute("SELECT * FROM scores WHERE owner={owner} AND started={started} AND week={week}".\
			format(owner=ownerId, started=1, week=week))
		started.append(c.fetchall())

		players=[]
		#Get Starters
		for start in started[0]:
			player=FantasyPlayer()
			player.scoreQueryToPlayer(start)
			players.append(player)

		accTable=FantasyStatTable()
		accTable.description=str("Projection Accuracy for "+ffScraper.leagueMembers[ownerId-1]+ " in Week "+str(week))
		accTable.tableHeaders=["Score","Projection","+/-"]

		totalPlusMinus=0
		totalScored=0
		totalProjected=0

		#Get Scores, projections and +/-, and add them into formatted tables
		for each in players:
			newRow=FantasyStatRow()
			newRow.name=each.name
			newRow.stats.append(str(each.score))
			newRow.stats.append(str(each.projection))
			newRow.stats.append(intToPlusMinusHTML(each.score-each.projection))
			totalPlusMinus=totalPlusMinus+(each.score-each.projection)
			totalScored=totalScored+each.score
			totalProjected=totalProjected+each.projection
			accTable.rows.append(newRow)

		totalRow=FantasyStatRow()

		if verbosity == 1:
			totalRow.name=addHTMLClass("Week "+str(week)+" Total","bold")
			totalRow.stats=[addHTMLClass(str(totalScored), "bold"),addHTMLClass(str(totalProjected),"bold"),addHTMLClass(intToPlusMinusHTML(totalPlusMinus), "bold")]
		else:
			totalRow.name="Week "+str(week)+" Total"
			totalRow.stats=[str(totalScored),str(totalProjected),intToPlusMinusHTML(totalPlusMinus)]
		
		seasonPlusMinus = seasonPlusMinus+totalPlusMinus
		seasonProjected = seasonProjected+totalProjected
		seasonScored = seasonScored + totalScored

		accTable.rows.append(totalRow)

		tables.append(accTable)
		totalTable.rows.append(totalRow)

	if verbosity == 0:
		seasonTotalRow=FantasyStatRow()
		seasonTotalRow.name=addHTMLClass("Season Total","bold")
		seasonTotalRow.stats=[addHTMLClass(str(seasonScored),"bold"),addHTMLClass(str(seasonProjected),"bold"),addHTMLClass(intToPlusMinusHTML(seasonPlusMinus), "bold")]
		totalTable.rows.append(seasonTotalRow)

		return totalTable
	if verbosity == 1:
		return tables
	if verbosity == 2:
		seasonTotalRow=FantasyStatRow()
		seasonTotalRow.name=ffScraper.leagueMembers[ownerId-1]
		seasonTotalRow.stats=[str(seasonScored),str(seasonProjected),intToPlusMinusHTML(seasonPlusMinus)]
		return seasonTotalRow

#Calculate how each player on an owner's team did relative to projection (per season basis)
def calcPlayerProjectionAccuracy(ownerId):
	db = sqlite3.connect(ffScraper.DB_NAME)
	c=db.cursor()
	starters=[]

	for week in range(1,ffScraper.REG_SEASON_WEEKS+1):
		started=[]
		c.execute("SELECT * FROM scores WHERE owner={owner} AND started={started} AND week={week}".\
			format(owner=ownerId, started=1, week=week))
		started.append(c.fetchall())

		#Get Starters, miscStat will represent the number of starts
		for start in started[0]:
			starter=FantasyPlayer()
			starter.scoreQueryToPlayer(start)
			
			#If player is in list already (this assumes a team can't have two players with the same name and pos)
			if any((s.name == starter.name and s.position==starter.position) for s in starters):
				for s in starters:
					if s.name == starter.name and s.position == starter.position:
						s.projection=s.projection+starter.projection
						s.score=s.score+starter.score
						#Add up number of starts
						s.miscInt=s.miscInt+s.started
			#Else add player and adjust actual score and projection
			else:
				starter.miscInt=starter.started
				starters.append(starter)

	starterTable=FantasyStatTable()
	starterTable.description=str("Displaying Player Projection Accuracy for "+ffScraper.leagueMembers[ownerId-1])
	starterTable.tableHeaders=["Num Starts","Points Scored","Projected","Total +/-","Average +/- (per start)"]
	for each in sorted(starters, key=lambda s: (s.score-s.projection), reverse=True):
		starterRow=FantasyStatRow()
		starterRow.name = each.name
		starterRow.stats=[str(each.miscInt), str(each.score), str(each.projection), intToPlusMinusHTML(each.score-each.projection), intToPlusMinusHTML((each.score-each.projection)/each.miscInt)]
		starterTable.rows.append(starterRow)

	return starterTable



#TODO: Finish this after the total tables is done
def draftAnalysis(ownerId):
	#Get name of all players that were drafted
	db = sqlite3.connect(ffScraper.DB_NAME)
	c=db.cursor()
	drafted=[]
	draftRanking={}
	draftedPlayers=[]

	#drafted will be a dictionary with key of player name and value of POS+Ranking (Ex: RB2)
	c.execute("SELECT DISTINCT name,position,nflTeam FROM scores")


	c.execute("SELECT * FROM draftrecap WHERE owner={owner}".\
		format(owner=ownerId))
	drafted.append(c.fetchall())

	drafted=drafted[0]



	for draftee in drafted:
		player=FantasyPlayer()
		player.name=str(draftee[2])
		player.nflTeam=str(draftee[3])
		player.position=str(draftee[4])
		player.owner=str(draftee[5])
		player.printPlayer()

		#For each player, query for scores.










