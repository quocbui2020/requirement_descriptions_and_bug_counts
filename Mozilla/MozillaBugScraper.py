from bugbug import bugzilla, db
from bugbug import repository, db

# Download the latest version if the data set if it is not already downloaded
db.download(bugzilla.BUGS_DB)
db.download(repository.COMMITS_DB)

