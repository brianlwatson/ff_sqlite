#Currently using Python 2.7
from bs4 import BeautifulSoup
import urllib2 as urllib
import re
import sqlite3
import sys
import time
from multiprocessing import Process, Pool
import operator

# Leagues
# Stewart Family Bonding
#LEAGUE_ID="leagueId=523659" 
# Brian's Bimbos
LEAGUE_ID="leagueId=1781003"

# Utility Setup
MAX_THREADS = 8
projUrls = []
scoresUrls = []

# League information
leagueName=""
leagueMembers=[]
fantasyOwners=[]

# Scrape Info
PROJ_HOME="http://games.espn.com/ffl/tools/projections?"+LEAGUE_ID
SCORES_HOME="http://games.espn.com/ffl/leaders?"+LEAGUE_ID
CURRENT_YEAR="2017"
STANDINGS_HOME="http://games.espn.com/ffl/standings?"+LEAGUE_ID+"&seasonId="+CURRENT_YEAR
SCHEDULE_HOME="http://games.espn.com/ffl/schedule?"+LEAGUE_ID #+"&teamId=XX"
REG_SEASON_WEEKS=12
PAGES_TO_SCRAPE=6
#TODO - Add playoff scraping


# Points breakdown per team && week is at 
# http://games.espn.com/ffl/clubhouse?leagueId=1781003&teamId=6&scoringPeriodId=15&view=stats

# Object definitions
class PlayerScore:
	def __init__(self, name, nfl, pos, points, started, owner, week):
		self.name=name
		self.nflTeam=nfl
		self.position=pos
		self.pointsScored=points
		self.started=started
		self.fantasyOwner=owner
		self.week=week
	def printPlayerScore(self):
		print "(",self.week,")","Name:",self.name," Team:",self.nflTeam," Pos:",self.position," Points:",self.pointsScored, " Started:",self.started, " Owner:", self.fantasyOwner

class PlayerProjection:
	def __init__(self, name, nfl, pos, proj, owner, week):
		self.name=name
		self.nflTeam=nfl
		self.position=pos
		self.projPoints=proj
		self.fantasyOwner=owner
		self.week=week
	def printPlayerProj(self):
		print "(",self.week,")","Name:",self.name," Team:",self.nflTeam," Pos:",self.pos," Proj:",self.projPoints, " Owner:", self.fantasyOwner

class FantasyOwner:
	def __init__(self):
		self.teamName=""
		self.opponents=[]
		self.opponentIDs=[]
		self.scores=[]
		self.oppScores=[]
		self.wins=0
		self.losses=0
		self.ties=0
	def printOwner(self):
		print "Team: ",self.teamName, " (teamId="+str(leagueMembers.index(self.teamName)+1)+")"
		for i in range (1, REG_SEASON_WEEKS+1):
			print "Week:",i, str(self.scores[i-1])+"-"+str(self.oppScores[i-1]), " vs. ", self.opponents[i-1], " (teamId="+str(self.opponentIDs[i-1])+")"

# League scraping
class LeagueScraper:
	def getLeagueInfo(self):
		standingsScrape=urllib.urlopen(STANDINGS_HOME).read()
		soup=BeautifulSoup(standingsScrape, "html.parser")

		#Scrape League Name and League members (in order of their ownerID)
		global leagueName
		leagueName=str(soup.find_all("div", class_="nav-main-breadcrumbs")[0].find_all("a", href=re.compile("leagueoffice"))[0].text)
		teamNames=soup.find_all("div", class_="games-nav")[0].find_all("a", href=re.compile("teamId"))
		for team in teamNames:
			leagueMember=team.text[0:team.text.find("(")-1]
			leagueMembers.append(str(leagueMember))
	
	def scrapeOwners(self):
		for teamId in range(1,len(leagueMembers)+1):
			scheduleScrape=urllib.urlopen(SCHEDULE_HOME+"&teamId="+str(teamId))
			soup=BeautifulSoup(scheduleScrape, "html.parser")
			opponents=soup.find_all("table", class_="tableBody")[0].find_all("tr")
			owner=FantasyOwner()

			for each in opponents[1:]:
				trData = each.text.split("\n")
				
				#Row does not contain matchup info
				if len(trData) is 1:
					continue

				#Capture regular season data
				#Data from row split by \n format: [u'', u'Week X', u'W/L/T OwnerScore-OppScore', u'at\xa0', u'Team Name (WINS-LOSSES-TIES)', u'Owner Name', u''] 
				if "Week" in trData[1]:				
					#trData index 2 is W/L/T OwnerScore-OppScore
					if str(trData[2].split(" ")[0]) == "W":
						owner.wins=owner.wins+1
					elif str(trData[2].split(" ")[0]) == "L":
						owner.losses=owner.losses+1
					else:
						owner.ties=owner.ties+1

					owner.teamName=leagueMembers[teamId-1]
					owner.scores.append(trData[2].split(" ")[1].split("-")[0])
					owner.oppScores.append(trData[2].split(" ")[1].split("-")[1])

					#opp Name is index 4: u'Team Name (WINS-LOSSES-TIES)'
					owner.opponents.append(trData[4][0:trData[4].find("(")-1])
					owner.opponentIDs.append( leagueMembers.index(owner.opponents[-1])+1 )
			fantasyOwners.append(owner)
			#Capture playoff data
			#if "Round" in len(each.text.split("\n")):

# Score retrieval
class ScoreScraper:
	def __init__(self, db):
		self.c=db.cursor()
		self.c.execute('''DROP TABLE if exists scores''')
		self.c.execute('''CREATE TABLE if not exists scores (name text, nflTeam text, position text, points real, started integer, owner integer, week real)''')
	def updateDBScores(self,name,nflTeam,position,pointsScored,started,fantasyOwner,week):
		self.c.execute("INSERT INTO scores VALUES (?,?,?,?,?,?,?)",(name,nflTeam,position,pointsScored,started,fantasyOwner,week))
	def getScoresUrls(self):
		print "Getting scores URLs..."
		for week in range (1, REG_SEASON_WEEKS + 1):
			for page in range(0,PAGES_TO_SCRAPE):
				pageStart=50*page
				pageIndex="&startIndex="+str(pageStart)
				scoresUrl=SCORES_HOME+"&scoringPeriodId="+str(week)+"&seasonId="+CURRENT_YEAR+pageIndex
				scoresUrls.append(scoresUrl)

	def parallelize(self):
		startTime = int(round(time.time()))
		# pool = Pool(processes=4)
		sys.stdout.write("Retrieving scores.")
		sys.stdout.flush()
		allPlayers = pool.map(fetchScoresPage, scoresUrls)
		endTime = int(round(time.time()))
		for lst in allPlayers:
			for ps in lst:
				self.updateDBScores(ps.name, ps.nflTeam, ps.position, ps.pointsScored, ps.started, ps.fantasyOwner, ps.week)
		print "\nScores took " + str(endTime - startTime) + " seconds"

def fetchScoresPage(scoresUrl):
	sys.stdout.write('.')
	sys.stdout.flush()
	scoresScrape=urllib.urlopen(scoresUrl).read()
	soup=BeautifulSoup(scoresScrape, "html.parser")
	players=soup.find_all("tr", class_="pncPlayerRow")
	#Assuming [URL]&scoringPeriodId=XX&seasonId=YYYY&startIndex=ZZZ	
	week = scoresUrl.split("&")[1].split("=")[1]
	return parseScores(players, week)

def parseScores(players, week):
	currScores = []
	for scrapedPlayer in players:
		playerInfo=scrapedPlayer.find_all("td",class_="playertablePlayerName")[0].text.replace(u'\xa0', u' ')
		playerName=playerInfo.split(",")[0].replace("*", "")

		if "D/ST" in playerName:
			playerNFL=playerName.split(" ")[0]
			playerPos="D/ST"
			playerName=playerName.split(" ")[0]+" "+playerName.split(" ")[1]
		else:
			playerNFL=playerInfo.split(",")[1][1:].split(" ")[0]
			playerPos=playerInfo.split(",")[1][1:].split(" ")[1]

		try:
			#use regex to search for owner id number, get the link using href element value
			ownerLeague=scrapedPlayer.find_all("a", href=re.compile("clubhouse"))[0]["href"]
			#formatted as /ffl/clubhouse?leagueId=XXXXX&teamId=Y&seasonId=ZZZZ
			# lazy parse to get teamId=Y
			playerOwner=ownerLeague.split("&")[1].split("=")[-1]
		except:
			playerOwner=0

		pointsScored=scrapedPlayer.find_all("td",class_="playertableStat")[-1].text

		# TODO: get yards, tds, etc
		#If you wanted all of the numerical stats, you could find them in 
		#for pStat in playerProj:
		#	print pStat.text

		started = 0
		if playerOwner != 0:
			clubUrl="http://games.espn.com/ffl/clubhouse?"+LEAGUE_ID+"&teamId="+str(playerOwner)+"&scoringPeriodId="+str(week)+"&seasonId="+CURRENT_YEAR
			clubScrape=urllib.urlopen(clubUrl).read()
			clubSoup=BeautifulSoup(clubScrape, "html.parser")
			lineup=clubSoup.find_all("tr", class_="pncPlayerRow")
			for player in lineup:
				if playerName in player.text:
					lineupPos=player.find("td", class_=re.compile('.*playerSlot.*'))
					if "Bench" not in lineupPos.text:
						started = 1

		ps=PlayerScore(playerName,playerNFL,playerPos,pointsScored,started,playerOwner,week)
		currScores.append(ps)
		# ps.printPlayerScore()
	return currScores

# Projection retrieval
class ProjScraper:
	def __init__(self, db):
		self.c=db.cursor()
		self.c.execute('''DROP TABLE if exists projections''')
		self.c.execute('''CREATE TABLE if not exists projections (name text, nflTeam text, position text, proj real, owner integer, week real)''')
	def updateDBProj(self,name, nflTeam,position,proj,owner, week):
		self.c.execute("INSERT INTO projections VALUES (?,?,?,?,?,?)",(name,nflTeam,position,proj,owner,week))
	def commitDB(self):
		#self.c.execute('''COMMIT''')#
		print ""
	def getProjUrls(self):
		print "Getting Projection URLS..."
		for week in range(1,REG_SEASON_WEEKS+1):
			# 5 pages of projections * 40 players should be enough for now
			for page in range(0,PAGES_TO_SCRAPE):
				if page is 0:
					pageIndex=""
				else:
					pageStart=40*page
					pageIndex="&startIndex="+str(pageStart)
				projUrl=PROJ_HOME+"&scoringPeriodId="+str(week)+"&seasonId="+CURRENT_YEAR+pageIndex
				projUrls.append(projUrl)

	def parallelize(self):
		startTime = int(round(time.time()))
		sys.stdout.write("Gathering projections.")
		sys.stdout.flush()
		allPlayers = pool.map(fetchProjPage, projUrls)
		endTime = int(round(time.time()))
		for lst in allPlayers:
			for pp in lst:
				self.updateDBProj(pp.name, pp.nflTeam, pp.position, pp.projPoints, pp.fantasyOwner, pp.week)
		print "\nProjections took " + str(endTime - startTime) + " seconds"

def fetchProjPage(projUrl):
	sys.stdout.write('.')
	sys.stdout.flush()
	projScrape=urllib.urlopen(projUrl).read()
	soup=BeautifulSoup(projScrape, "html.parser")
	week = soup.find("div", class_="games-pageheader").text.split(" ")[2]
	players=soup.find_all("tr", class_="pncPlayerRow")
	return parseProjections(players, week)

def parseProjections(players, week):
	currPlayers = []
	for playerScrape in players:
		#playertablePlayerName formatted in projections table as: {"FirstName LastName", "NFL Team", "Pos"}
		playerInfo=playerScrape.find_all("td",class_="playertablePlayerName")[0].text.replace(u'\xa0', u' ')
		#get player name and remove asterisk
		playerName=playerInfo.split(",")[0].replace("*", "")

		if "D/ST" in playerName:
			playerNFL=playerName.split(" ")[0]
			playerPos="D/ST"
			playerName=playerName.split(" ")[0]+" "+playerName.split(" ")[1]
		else:
			playerNFL=playerInfo.split(",")[1][1:].split(" ")[0]
			playerPos=playerInfo.split(",")[1][1:].split(" ")[1]

		try:
			#use regex to search for owner id number, get the link using href element value
			ownerLeague=playerScrape.find_all("a", href=re.compile("clubhouse"))[0]["href"]
			#formatted as /ffl/clubhouse?leagueId=XXXXX&teamId=Y&seasonId=ZZZZ
			# lazy parse to get teamId=Y
			playerOwner=ownerLeague.split("&")[1].split("=")[-1]
		except:
			playerOwner=0

		playerProj=playerScrape.find_all("td",class_="playertableStat")[-1].text
		#If you wanted all of the numerical stats, you could find them in 
		#for pStat in playerProj:
		#	print pStat.text

		pp=PlayerProjection(playerName,playerNFL,playerPos,playerProj,playerOwner,week)
		currPlayers.append(pp)
		# pp.printPlayerProj()
	return currPlayers


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
	db = sqlite3.connect(LEAGUE_ID.split("=")[-1]+".sqlite")
	c=db.cursor()
	result = []
	# for ownerId in range(1,len(fantasyOwners)+1):
	for week in range(1,REG_SEASON_WEEKS+1):
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
			pp = PlayerProjection(name,nflTeam,pos,proj,owner,week)
			projTeam.owner = owner
			projTeam.week = week
			projTeam.addToTeam(pp)
		projTeams.append(projTeam)
	for team in projTeams:
		team.composeBestProjTeam()
		team.printBestProjTeam()

def main():
	if "-help" in sys.argv:
		print "USAGE: python scraper.py [-scrape] [-games] [-project=<teamId>]"
		return
	
	#Initialization
	leagueScraper=LeagueScraper()
	leagueScraper.getLeagueInfo()
	print "Currently Configured for:",leagueName, "("+LEAGUE_ID+")"
	leagueScraper.scrapeOwners()


	# Scrape first for fresh data if other args are given
	#Now have to run "python scraper.py -scrape" to enact scraping
	if "-scrape" in sys.argv:
		# db = sqlite3.connect(filter(str.isalnum, str(leagueName))+".sqlite")
		db = sqlite3.connect(LEAGUE_ID.split("=")[-1]+".sqlite")
		pool = Pool(processes=MAX_THREADS)

		#Scores
		projScraper=ProjScraper(db)
		projScraper.getProjUrls()
		projScraper.parallelize()

		#Projections
		scoreScraper=ScoreScraper(db)
		scoreScraper.getScoresUrls()
		scoreScraper.parallelize()

		db.commit()
		db.close()

	# print game outcomes
	if "-games" in sys.argv:
		for owner in fantasyOwners:
			owner.printOwner(), "\n\n"

	# print best projected lineup for a given ownerId
	proj = re.compile("-project=\d+")
	for arg in sys.argv:
		if proj.match(arg):
			teamId = arg.split("=")[1]
			getBestProjLineup(int(teamId))
			break

if __name__ == "__main__":
    main()
