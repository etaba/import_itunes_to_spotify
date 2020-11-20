# Bottle app do import your Itunes playlists into Spotify

Install dependencies with

    $ pip install -r requirements.txt

Store your spotify credentials as environment variables

    export SPOTIPY_CLIENT_ID=<yourClientId>
    export SPOTIPY_CLIENT_SECRET=<yourClientSecret>

If you only want to import some of the itunes libraries, list them in `SELECTED_PLAYLISTS`. Otherwise leave it empty and all itunes playlists will be imported.

Start server with

    $ python import_itunes.py 

Clicking the "Dry run" link will search spotify for all the itunes songs and report at the end which songs could not be found.

Clicking the "Import" link will import the playlists and report which songs could not be found.

open http://localhost:8080 in a browser