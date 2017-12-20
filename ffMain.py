import sys
import sqlite3
import re

import ffScraper
import ffStats



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

	# print best projected lineup for a given ownerId
	proj = re.compile("-project=\d+")
	for arg in sys.argv:
		if proj.match(arg):
			teamId = arg.split("=")[1]
			ffStats.getBestProjLineup(int(teamId))
			break

if __name__ == "__main__":
    main()

    