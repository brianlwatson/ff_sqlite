import sys
import sqlite3
import re

import ffScraper
import ffStats

htmlStrings=[]

def writeHTMLOut():
	htmlDoc="<html>\n  <head><title>"+str(ffScraper.leagueName)+"</title><link rel=\"stylesheet\" type=\"text/css\" href=\"fantasy.css\"></head>"
	for htmlOut in htmlStrings:
		htmlDoc=htmlDoc+htmlOut
	htmlDoc=htmlDoc+"\n</html>"

	file=open( (filter(str.isalnum, str(ffScraper.leagueName))+".html"), "w")
	file.write(htmlDoc)
	file.close


def main():

	if "-help" in sys.argv:
		print "USAGE: python scraper.py [-scrape] [-games] [-project=<teamId>]"
		return
	
	#Initialization
	leagueScraper=ffScraper.LeagueScraper()
	leagueScraper.getLeagueInfo()
	print "Currently Configured for:", ffScraper.leagueName, "("+ffScraper.LEAGUE_ID+")"
	leagueScraper.scrapeOwners()


	# Scrape first for fresh data if other args are given
	#Now have to run "python scraper.py -scrape" to enact scraping
	if "-scrape" in sys.argv:
		# db = sqlite3.connect(filter(str.isalnum, str(leagueName))+".sqlite")
		db = sqlite3.connect(ffScraper.LEAGUE_ID.split("=")[-1]+".sqlite")

		#Scores
		projScraper=ffScraper.ProjScraper(db)
		projScraper.getProjUrls()
		projScraper.parallelize()

		#Projections
		scoreScraper=ffScraper.ScoreScraper(db)
		scoreScraper.getScoresUrls()
		scoreScraper.parallelize()

		db.commit()
		db.close()

	# print game outcomes
	if "-games" in sys.argv:
		for owner in ffScraper.fantasyOwners:
			owner.printOwner(), "\n\n"

	if "-threshold" in sys.argv:
		for threshold in [15,20,25,30,35]:
			pointsTable=ffStats.FantasyStatTable()
			pointsTable.description="Games with a "+str(threshold)+" point scorer"
			pointsTable.tableHeaders=["Games For","Games Against"]
			for ownerId in range(1,len(ffScraper.leagueMembers)+1):
				pointsTable.rows.append(ffStats.getGamesForAgainst(ownerId,threshold))
			tableOut=pointsTable.getHtmlTable("threshold"+str(threshold))
			htmlStrings.append(tableOut)


	if "-totalprojacc" in sys.argv:
		for ownerId in range(1,len(ffScraper.leagueMembers)+1):
			resTable=ffStats.calcProjectionAccuracy(ownerId,0)
			htmlStrings.append(resTable.getHtmlTable("totalprojacc"))

	if "-allprojacc" in sys.argv:
		projTable=ffStats.FantasyStatTable()
		projTable.description=str("Projection Accuracy for "+ffScraper.leagueName)
		projTable.tableHeaders=["Score","Projection","+/-"]

		for ownerId in range(1, len(ffScraper.leagueMembers)+1):
			projTable.rows.append(ffStats.calcProjectionAccuracy(ownerId,2))
		htmlStrings.append(projTable.getHtmlTable("allprojacc"))

	proj = re.compile("-projacc=\d+")
	for arg in sys.argv:
		if proj.match(arg):
			teamId = arg.split("=")[1]
			resTables=ffStats.calcProjectionAccuracy(int(teamId),1)
			for table in resTables:
				htmlStrings.append(table.getHtmlTable("projacc"))
			break

	# print best projected lineup for a given ownerId
	proj = re.compile("-project=\d+")
	for arg in sys.argv:
		if proj.match(arg):
			teamId = arg.split("=")[1]
			ffStats.getBestProjLineup(int(teamId))
			break



	#Write out to HTML if stats have been added to the html list
	if len(htmlStrings) > 0:
		writeHTMLOut()

if __name__ == "__main__":
    main()

