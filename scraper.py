#Currently using Python 2.7
from bs4 import BeautifulSoup
import urllib
import re
import sqlite3
import sys

# Stewart Family Bonding
# LEAGUE_ID="leagueId=523659" 

# Brian's Bimbos
LEAGUE_ID="leagueId=1781003"

PROJ_HOME="http://games.espn.com/ffl/tools/projections?"+LEAGUE_ID
SCORES_HOME="http://games.espn.com/ffl/leaders?"+LEAGUE_ID

CURRENT_YEAR="2017"
REG_SEASON_WEEKS=13
PAGES_TO_SCRAPE=6
PROJ_TOTAL = str(PAGES_TO_SCRAPE * 40 * REG_SEASON_WEEKS)
SCORES_TOTAL = str((PAGES_TO_SCRAPE * 50 * REG_SEASON_WEEKS) + 1200)

# Points breakdown per team && week is at 
# http://games.espn.com/ffl/clubhouse?leagueId=1781003&teamId=6&scoringPeriodId=15&view=stats

allPlayers = []

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
		self.pos=pos
		self.projPoints=proj
		self.fantasyOwner=owner
		self.week=week
	def printPlayerProj(self):
		print "(",self.week,")","Name:",self.name," Team:",self.nflTeam," Pos:",self.pos," Proj:",self.projPoints, " Owner:", self.fantasyOwner

class ScoreScraper:
	def __init__(self, db):
		self.c=db.cursor()
		self.c.execute('''DROP TABLE if exists scores''')
		self.c.execute('''CREATE TABLE if not exists scores (name text, nflTeam text, position text, points real, started integer, owner integer, week real)''')
	def updateDBScores(self,name,nflTeam,position,pointsScored,started,fantasyOwner,week):
		self.c.execute("INSERT INTO scores VALUES (?,?,?,?,?,?,?)",(name,nflTeam,position,pointsScored,started,fantasyOwner,week))
	def scrapeScores(self):
		counter = 0
		for week in range (1, REG_SEASON_WEEKS + 1):
			for page in range(0,PAGES_TO_SCRAPE):
				pageStart=50*page
				pageIndex="&startIndex="+str(pageStart)
				scoresUrl=SCORES_HOME+"&scoringPeriodId="+str(week)+"&seasonId="+CURRENT_YEAR+pageIndex
				scoresScrape=urllib.urlopen(scoresUrl).read()
				soup=BeautifulSoup(scoresScrape, "html.parser")
				players=soup.find_all("tr", class_="pncPlayerRow")

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

					self.updateDBScores(playerName,playerNFL,playerPos,pointsScored,started,playerOwner,week)
					ps=PlayerScore(playerName,playerNFL,playerPos,pointsScored,started,playerOwner,week)
					# ps.printPlayerScore()
					counter += 1
					print "Gathering actual scores... (" + str(counter) + " / ~" + SCORES_TOTAL + ")\r",

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
	def scrapeProj(self):
		counter = 0
		for week in range(1,REG_SEASON_WEEKS+1):
			# 5 pages of projections * 40 players should be enough for now
			for page in range(0,PAGES_TO_SCRAPE):
				if page is 0:
					pageIndex=""
				else:
					pageStart=40*page
					pageIndex="&startIndex="+str(pageStart)
				projUrl=PROJ_HOME+"&scoringPeriodId="+str(week)+"&seasonId="+CURRENT_YEAR+pageIndex
				#&startIndex=40
				projScrape=urllib.urlopen(projUrl).read()
				soup=BeautifulSoup(projScrape, "html.parser")
				
				players=soup.find_all("tr", class_="pncPlayerRow")

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

					self.updateDBProj(playerName,playerNFL,playerPos,playerProj,playerOwner,week)
					pp=PlayerProjection(playerName,playerNFL,playerPos,playerProj,playerOwner,week)
					# pp.printPlayerProj()
					# sys.stdout.write(".")
					counter += 1
					print "Gathering projections... (" + str(counter) + " / " + PROJ_TOTAL + ")\r",

db = sqlite3.connect(LEAGUE_ID.split("=")[-1]+".sqlite")
# Projections
print "Gathering projections... (0 / " + str(PROJ_TOTAL) + ")\r",
projScraper=ProjScraper(db)
projScraper.scrapeProj()
print

# Scores
print "Gathering actual scores... (0 / ~" + str(SCORES_TOTAL) + ")\r",
scoreScraper=ScoreScraper(db)
scoreScraper.scrapeScores()
print

db.commit()
db.close()

