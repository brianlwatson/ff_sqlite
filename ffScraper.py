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
DB_NAME=LEAGUE_ID.split("=")[-1]+".sqlite"
PROJ_HOME="http://games.espn.com/ffl/tools/projections?"+LEAGUE_ID
SCORES_HOME="http://games.espn.com/ffl/leaders?"+LEAGUE_ID
STANDINGS_HOME="http://games.espn.com/ffl/standings?"+LEAGUE_ID+"&seasonId="+CURRENT_YEAR
SCHEDULE_HOME="http://games.espn.com/ffl/schedule?"+LEAGUE_ID #+"&teamId=XX"
SETTINGS_HOME="http://games.espn.com/ffl/leaguesetup/settings?"+LEAGUE_ID
PAGES_TO_SCRAPE=20
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
lineupConfig={}
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
		print "Team: ",self.teamName, str(self.wins)+"-"+str(self.losses)+"-"+str(self.ties), " (teamId="+str(leagueMembers.index(self.teamName)+1)+")"
		for i in range (1, REG_SEASON_WEEKS+1):
			print "Week:",i, str(self.scores[i-1])+"-"+str(self.oppScores[i-1]), " vs. ", self.opponents[i-1], " (teamId="+str(self.opponentIDs[i-1])+")"

# League scraping
class LeagueScraper:
	def __init__(self, db):
		self.c=db.cursor()
	def getLeagueInfo(self):
		standingsScrape=urllib.urlopen(STANDINGS_HOME).read()
		soup=BeautifulSoup(standingsScrape, "html.parser")

		#Scrape League Name and League members (in order of their ownerID)
		global leagueName
		leagueName=str(soup.find_all("div", class_="nav-main-breadcrumbs")[0].find_all("a", href=re.compile("leagueoffice"))[0].text)
		self.c.execute('''DROP TABLE if exists leagueMisc''')
		self.c.execute('''CREATE TABLE if not exists leagueMisc (name text)''')
		self.c.execute("INSERT INTO leagueMisc VALUES (?)", (str(leagueName),))


		teamNames=soup.find_all("div", class_="games-nav")[0].find_all("a", href=re.compile("teamId"))
		for team in teamNames:
			leagueMember=team.text[0:team.text.find("(")-1]
			leagueMembers.append(str(leagueMember))

		#Scrape Number of starters at each position
		settingsScrape=urllib.urlopen(SETTINGS_HOME).read()
		soup=BeautifulSoup(settingsScrape, "html.parser")

		#Get number of starters for each position in the league and write to lineupConfig sqlite table
		self.c.execute('''DROP TABLE if exists lineupConfig''')
		self.c.execute('''CREATE TABLE if not exists lineupConfig (position text, starters int)''')

		global lineupConfig
		rosterConfig=soup.find_all("div", class_="leagueSettingsSection")[1].find_all("tr")
		for each in rosterConfig[3:-1]:
			lineupConfig[str(each.find_all("td")[0].text.split("(")[1][:-1])] = int(each.find_all("td")[1].text)
			self.c.execute("INSERT INTO lineupConfig VALUES (?,?)",(str(each.find_all("td")[0].text.split("(")[1][:-1]),int(each.find_all("td")[1].text)))


	def loadLeagueInfo(self):
		self.c.execute('''SELECT * from lineupConfig''')
		lineup={}

		for each in self.c.fetchall():
			lineup[str(each[0])]=each[1]

		global lineupConfig
		global leagueMembers
		global leagueName

		lineupConfig=lineup

		members=[]
		self.c.execute('''SELECT name from owners''')
		for each in self.c.fetchall():
			members.append(str(each[0]))
	

		self.c.execute('''SELECT * from leagueMisc''')
		leagueName=self.c.fetchall()[0][0]
		leagueMembers=members



	def scrapeOwners(self):
		self.c.execute('''CREATE TABLE if not exists owners (name text, wins int, losses int, ties int)''')

		for week in range(1, REG_SEASON_WEEKS+1):
			self.c.execute("ALTER TABLE owners ADD COLUMN "+"Week"+str(week)+"_Recap text")

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

			ownerTuple= (owner.teamName, owner.wins, owner.losses, owner.ties)
			for idx,each in enumerate(owner.scores):
				weekRecap=str(each)+str("-")+str(owner.oppScores[idx])+str(" oppId=")+str(owner.opponentIDs[idx])
				ownerTuple=ownerTuple+(weekRecap,)
			self.c.execute(("INSERT INTO owners VALUES (?,?,?,?"+str(",?"*(REG_SEASON_WEEKS))+")"),ownerTuple)

			#Capture playoff data
			#if "Round" in len(each.text.split("\n")):

	def loadOwners(self):
		self.c.execute("SELECT * from owners")
		global fantasyOwners
		temp=[]
		fOwners=[]
		temp.append(self.c.fetchall())

		for owner in temp[0]:
			fOwner=FantasyOwner()
			fOwner.teamName=owner[0]
			fOwner.wins=owner[1]
			fOwner.losses=owner[2]
			fOwner.ties=owner[3]
			for i in range(4,4+REG_SEASON_WEEKS):
				score=str(owner[i].split(" ")[0])
				oppId=str(owner[i].split(" ")[1]).split("=")[-1]
				myScore=score.split("-")[0]
				oppScore=score.split("-")[-1]
				fOwner.opponentIDs.append(oppId)
				fOwner.scores.append(float(myScore))
				fOwner.oppScores.append(float(oppScore))
				fOwner.opponents.append(leagueMembers[int(oppId)-1])
			fOwners.append(fOwner)

		fantasyOwners=fOwners


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


	def createTotalTables(self):
		self.c.execute('''DROP TABLE if exists totals''')
		self.c.execute('''CREATE TABLE if not exists totals (name text, nflTeam text, position text, totalScore real)''')

		self.c.execute("SELECT DISTINCT name,position,nflTeam FROM scores")
		players=[]
		players.append(self.c.fetchall())

		#For each distinct player, query and get their total points
		for each in players[0]:
			pName=each[0]
			pPos=each[1]
			pTeam=each[2]
			pQuery=(pName,pTeam,pPos)
			self.c.execute("SELECT * FROM scores WHERE name=? AND nflTeam=? AND position=?", pQuery)

			pQueries=self.c.fetchall()
			pTotal=0

			for res in pQueries:
				pTotal=pTotal+res[4]

			totalQuery=pQuery+(pTotal,)
			self.c.execute("INSERT INTO totals VALUES (?,?,?,?)",(totalQuery))


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

class DraftRecapScraper:
	def __init__(self, db):
		self.c=db.cursor()
		self.c.execute('''DROP TABLE if exists draftrecap''')
		self.c.execute('''CREATE TABLE if not exists draftrecap (round int, overallPick int, name text, nflTeam text, position text, owner integer, posRank integer)''')
	def updateDBDraft(self, rnd, overallPick, name, nflTeam, position, owner, posRank):
		self.c.execute("INSERT INTO draftrecap VALUES (?,?,?,?,?,?,?)",(rnd, overallPick, name, nflTeam, position, owner, posRank))
	def scrapeDraftRecap(self):
		htmlStrings = []
		maxOwner = 0
		recapUrl = "http://games.espn.com/ffl/tools/draftrecap?" + LEAGUE_ID
		recapScrape=urllib.urlopen(recapUrl).read()
		soup=BeautifulSoup(recapScrape, "html.parser")
		picks = soup.find_all("tr", class_="tableBody")

		numPicked={}
		for pos in lineupConfig:
			numPicked[pos]=0

		for player in picks:
			ownerLeague = player.find_all("a", href=re.compile("clubhouse"))[0]["href"]
			owner = ownerLeague.split("&")[1].split("=")[-1]

			pick = ""
			count = 0
			for c in player.text:
				if c.isdigit():
					pick += c
					count += 1
				else:
					break

			playerName = player.text[count:].split(",")[0].replace("*", "")

			if "D/ST" in playerName:
				playerNFL = playerName.split(" ")[0]
				playerPos = "D/ST"
				playerName = playerName.split(" ")[0] + " D/ST"
			else:
				playerInfo = player.find_all("td")[1].text.replace(u'\xa0', u' ')
				playerNFL = playerInfo.split(" ")[-2]
				playerPos = playerInfo.split(" ")[-1]

			# TODO: Fix round count
			rnd = 0
			numPicked[playerPos]=numPicked[playerPos]+1
			# print pick + ". " +playerName + " (" + playerPos + ", " + playerNFL + ")" + ", Owner: " + owner
			html = "<span>" + pick + ". " +playerName + " (" + playerPos + ", " + playerNFL + ")" + ", Owner: " + owner + "</span><br>"
			self.updateDBDraft(rnd, pick, playerName, playerNFL, playerPos, owner, numPicked[playerPos])
			htmlStrings.append(html)
		return htmlStrings

pool = Pool(processes=MAX_THREADS)
