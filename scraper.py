#Currently using Python 2.7
from bs4 import BeautifulSoup
import urllib
import re
import sqlite3

LEAGUE_ID="leagueId=523659"
PROJ_HOME="http://games.espn.com/ffl/tools/projections?"+LEAGUE_ID
CURRENT_YEAR="2017"
REG_SEASON_WEEKS=13



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

class ProjScraper:
	def __init__(self, db):
		self.c=db.cursor()
		self.c.execute('''DROP TABLE if exists projections''')
		self.c.execute('''CREATE TABLE if not exists projections (name text, nflTeam text, position text, proj real, owner real,week real)''')
	def updateDBProj(self,name, nflTeam,position,proj,owner, week):
		self.c.execute("INSERT INTO projections VALUES (?,?,?,?,?,?)",(name,nflTeam,position,proj,owner,week))
	def commitDB(self):
		#self.c.execute('''COMMIT''')#
		print ""
	def scrapeProj(self):
		for week in range(1,REG_SEASON_WEEKS+1):
			#5 pages of projections * 40 players should be enough for now
			for page in range(0,6):
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
						playerOwner=-1

					playerProj=playerScrape.find_all("td",class_="playertableStat")[-1].text
					#If you wanted all of the numerical stats, you could find them in 
					#for pStat in playerProj:
					#	print pStat.text

					self.updateDBProj(playerName,playerNFL,playerPos,playerProj,playerOwner,week)
					pp=PlayerProjection(playerName,playerNFL,playerPos,playerProj,playerOwner,week)
					pp.printPlayerProj()

db = sqlite3.connect(LEAGUE_ID.split("=")[-1]+".sqlite")
projScraper=ProjScraper(db)
projScraper.scrapeProj()
projScraper.commitDB()
db.commit()
db.close()

