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
#REG_SEASON_WEEKS=13

# Brian's Bimbos
LEAGUE_ID="leagueId=1781003"
REG_SEASON_WEEKS=12

#Allow for scraping of decimal values
USE_DECIMALS=0

CURRENT_YEAR="2017"

# Scrape Info
PROJ_HOME="http://games.espn.com/ffl/tools/projections?"+LEAGUE_ID
SCORES_HOME="http://games.espn.com/ffl/leaders?"+LEAGUE_ID
STANDINGS_HOME="http://games.espn.com/ffl/standings?"+LEAGUE_ID+"&seasonId="+CURRENT_YEAR
SCHEDULE_HOME="http://games.espn.com/ffl/schedule?"+LEAGUE_ID #+"&teamId=XX"
PAGES_TO_SCRAPE=6
# Points breakdown per team && week is at 
# http://games.espn.com/ffl/clubhouse?leagueId=1781003&teamId=6&scoringPeriodId=15&view=stats


# Utilities
MAX_THREADS = 8
# pool = Pool(processes=MAX_THREADS)

#TODO - Add playoff scraping
projUrls = []
scoresUrls = []

# League information
leagueName=""
leagueMembers=[]
fantasyOwners=[]

class PlayerScores:
	def __init__(self, name, nfl, pos, proj, points, started, owner, week):
		self.name=name
		self.nflTeam=nfl
		self.position=pos
		self.projPoints=proj
		self.pointsScored=points
		self.started=started
		self.fantasyOwner=owner
		self.week=week
	def printPlayerProj(self):
		print "(",self.week,")","Name:",self.name," Team:",self.nflTeam," Pos:",self.pos," Proj:",self.projPoints, " Points:",self.pointsScored, " Started:",self.started, " Owner:", self.fantasyOwner

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
		# self.c.execute('''DROP TABLE if exists scores''')
		self.c.execute('''CREATE TABLE if not exists scores (name text, nflTeam text, position text, proj real, score real, started int, owner integer, week real)''')
	def updateDBScores(self,name,nflTeam,position,pointsScored,started,ownerId,week):
		if(pointsScored == "--"):
			pointsScored=0
		self.c.execute("UPDATE scores SET score=:score, started=:started WHERE owner=:owner AND week=:week AND name=:name", {"score": pointsScored, "started":started, "owner": ownerId, "week": float(week), "name":name})
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

		proj = 0.0
		ps=PlayerScores(playerName,playerNFL,playerPos,proj,pointsScored,started,playerOwner,week)
		currScores.append(ps)
	return currScores

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
		playerPoints = 0
		started = 0
		ps=PlayerScores(playerName,playerNFL,playerPos,playerProj,playerPoints,started,playerOwner,week)
		currPlayers.append(ps)
		# pp.printPlayerProj()
	return currPlayers


# Projection retrieval
class ProjScraper:
	def __init__(self, db):
		self.c=db.cursor()
		self.c.execute('''DROP TABLE if exists scores''')
		self.c.execute('''CREATE TABLE if not exists scores (name text, nflTeam text, position text, proj real, score real, started int, owner integer, week real)''')
	def updateDBProj(self,name, nflTeam,position,proj,points,started,owner, week):
		if proj == "--":
			proj = 0.0
		if not USE_DECIMALS:
			proj = round(float(proj))
		self.c.execute("INSERT INTO scores VALUES (?,?,?,?,?,?,?,?)",(name,nflTeam,position,proj,points,started,owner,week))
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
			for ps in lst:
				self.updateDBProj(ps.name, ps.nflTeam, ps.position, ps.projPoints, ps.pointsScored, ps.started, ps.fantasyOwner, ps.week)
		print "\nProjections took " + str(endTime - startTime) + " seconds"

pool = Pool(processes=MAX_THREADS)
