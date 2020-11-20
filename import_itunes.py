# https://github.com/plamere/spotipy/blob/master/spotipy/util.py
# http://www.acmesystems.it/python_httpd


from bottle import route, run, request
import spotipy, json, os
from spotipy import oauth2
import xml.etree.ElementTree as ET
import re
import pdb

PORT_NUMBER = 8080
SPOTIPY_CLIENT_ID = os.environ['SPOTIPY_CLIENT_ID']
SPOTIPY_CLIENT_SECRET = os.environ['SPOTIPY_CLIENT_SECRET']
SPOTIPY_REDIRECT_URI = 'http://localhost:8080'
SCOPE = 'user-library-read playlist-modify-private playlist-modify-public'
CACHE = '.spotipyoauthcache'
SELECTED_PLAYLISTS = []

sp_oauth = oauth2.SpotifyOAuth( SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET,SPOTIPY_REDIRECT_URI,scope=SCOPE,cache_path=CACHE )

@route('/')
def index():
    access_token = ""
    token_info = sp_oauth.get_cached_token()

    if token_info:
        print("Found cached token!")
        access_token = token_info['access_token']
    else:
        url = request.url
        code = sp_oauth.parse_response_code(url)
        print(f"code {code}")
        if code != 'http://localhost:8080/':
            print("Found Spotify auth code in Request URL! Trying to get valid access token...")
            token_info = sp_oauth.get_access_token(code)
            access_token = token_info['access_token']

    if access_token:
        print("Access token available!")
        return f"<a href='/dry_run/{access_token}'>Dry run</a><br><a href='/import_to_spotify/{access_token}'>Import</a>"
    else:
        return html_for_login_button()

@route('/import_to_spotify/<access_token>')
def import_to_spotify(access_token):
    sp = spotipy.Spotify(access_token)
    sp_user_id = sp.current_user()['id']

    with open('playlists.json','r+') as playlists_json, open('tracks.json','r+') as tracks_json:
        playlists = json.load(playlists_json)
        tracks = json.load(tracks_json)

        existing_playlists = [item['name'] for item in sp.user_playlists(sp_user_id)['items']]

        for playlist_name in pl_of_interest(playlists):
            print("PLAYLIST: " + playlist_name)
            # skip if playlist already exists in spotify
            if playlist_name in existing_playlists:
                print(f"skipping playlist which already exists in spotify: {playlist_name}")
                continue

            # otherwise create playlist
            new_playlist = sp.user_playlist_create(sp_user_id, playlist_name, public=False)

            # add tracks in batches of 75
            uris = []
            for i, tid in enumerate(playlists[playlist_name]):
                if tid not in tracks.keys():
                    continue

                track = tracks[tid]
                if 'spotify_uri' in track.keys():
                    uris.append(track['spotify_uri'])

                if (len(uris) > 74 or i == len(playlists[playlist_name])-1):
                    sp.user_playlist_add_tracks(sp_user_id, new_playlist['id'], uris)
                    uris = []
    return 'Done'

@route('/dry_run/<access_token>')
def dry_run(access_token):
    sp = spotipy.Spotify(access_token)
    # find_track_uris(sp)
    return missing_report()

def html_for_login_button():
    auth_url = get_auth_url()
    html_login_button = "<a href='" + auth_url + "'>Login to Spotify</a>"
    return html_login_button

def get_auth_url():
    auth_url = sp_oauth.get_authorize_url()
    return auth_url

def create_spotify_playlist(username, name, tracks):
    sp = get_spotify_client()
    user = sp.current_user()['id']
    new_playlist = sp.user_playlist_create(user, name, public=False)
    sp.user_playlist_add_tracks(user, new_playlist, tracks)
    # get track urls
    for track in tracks:
        artist = songs[track]['artist']
        sp_track_id = find_spotify_track(**songs[track])

def find_track_uris(sp):
    with open('playlists.json','r+') as playlists_json, open('tracks.json','r+') as tracks_json:
        playlists = json.load(playlists_json)
        tracks = json.load(tracks_json)
        tracks_json.seek(0)
        for _, track in tracks.items():
            if 'spotify_uri' not in track.keys():
                # find uri from spotify, store it in tracks
                uri = find_spotify_track(sp, track['artist'], track['name'])
                if uri != None:
                    print("FOUND!!!")
                    track['spotify_uri'] = uri

        json.dump(tracks, tracks_json)
        tracks_json.truncate()


def find_spotify_track(sp, artist, track, attempt=1):
    q = f"artist:{artist} track:{track}"
    results = spotify_track_search(sp, q)

    if results != None:
        return results

    print(f'couldnt find:   {q}')

    # try replacing non alphanumeric chars with space
    artist_space = re.sub(r'[^a-zA-Z\d\s:]', ' ', artist)
    track_space = re.sub(r'[^a-zA-Z\d\s:]', ' ', track)
    q2 = f"artist:{artist_space} track:{track_space}"
    if q != q2:
        results = spotify_track_search(sp, q2)
        if results != None:
            return results
    print(f'couldnt find:   {q2}')

    # try removing non alphanumeric chars
    artist_no_space = re.sub(r'[^a-zA-Z\d\s:]', '', artist)
    name_no_space = re.sub(r'[^a-zA-Z\d\s:]', '', track)
    q3 = f"artist:{artist_no_space} track:{name_no_space}"
    if q != q3:
        results = spotify_track_search(sp, q3)
        if results != None:
            return results
    print(f'couldnt find:   {q3}')

    # try removing parenthesis and bracketed things
    q4 = remove_parenthesis_and_brackets(q)
    if q != q4:
        results = spotify_track_search(sp, q4)
        if results != None:
            return results
    print(f'couldnt find:   {q4}')

    # try removing features
    artist_no_feat = remove_feat(remove_parenthesis_and_brackets(artist))
    track_no_feat = remove_feat(remove_parenthesis_and_brackets(track))
    q5 = f"artist:{artist_no_feat} track:{track_no_feat}"
    if q5 != q4:
        results = spotify_track_search(sp, q5)
        if results != None:
            return results

    print(f'GIVING UP:   {q5}')
    return None

def spotify_track_search(sp, q):
    results = sp.search(q, limit=1, offset=0, type='track')

    if results['tracks']['total'] > 0:
        return results['tracks']['items'][0]['uri']
    else:
        return None

def remove_parenthesis_and_brackets(str):
    out = ''
    in_p = False
    in_b = False
    for i, c in enumerate(str):
        if c == '(':
            in_p = True
        elif c == ')':
            in_p = False
        elif c == '[':
            in_b = True
        elif c == ']':
            in_b = False
        if not in_p and not in_b and c != ')' and c != ']':
            out += c
    return out

def remove_feat(str):
    str = str.lower()
    synonyms = [' ft', ' feat']
    for synonym in synonyms:
        if synonym not in str:
            continue
        str = str[:str.find(synonym)]
    return str

def parse_itunes(itunes_location = 'itunes.xml'):
    # playlist name: [track id's]
    playlists = {}
    # track id: {name: track name, artist: track artist}
    songs = {}
    with open(itunes_location, 'r') as f, open('playlists.json','w+') as playlists_f, open('tracks.json','w+') as tracks_f:
        # create element tree object 
        tree = ET.parse(f)
      
        # get root element 
        music = tree.getroot() 

        # pdb.set_trace()
        tracks = found_playlist_section = False
        for item in music:
            if item.text == 'Tracks':
                tracks = True
                continue
            if item.text == 'Playlists':
                found_playlist_section = True
                tracks = False
                continue
            if tracks and not found_playlist_section:
                for key_or_dict in item:
                    if key_or_dict.tag == 'dict':
                        track_info = key_or_dict
                        for i in range(len(track_info)):
                            if track_info[i].text == 'Track ID':
                                curr_id = track_info[i+1].text
                            if track_info[i].text == 'Name':
                                curr_name = track_info[i+1].text
                            if track_info[i].text == 'Artist':
                                curr_artist = track_info[i+1].text
                                songs.update({curr_id: {'name': curr_name, 'artist': curr_artist}})
                                break
            if found_playlist_section:
                for playlist in item:
                    # playlist is a dict
                    for i in range(len(playlist)):
                        if playlist[i].text == 'Name':
                            curr_name = playlist[i+1].text
                        if playlist[i].text == 'Playlist Items':
                            curr_songs = []
                            for track in playlist[i+1]:
                                curr_songs.append(track[1].text)
                            playlists.update({curr_name: curr_songs})
                            break

        json.dump(playlists, playlists_f)
        json.dump(songs, tracks_f)

def pl_of_interest(playlists):
    if len(SELECTED_PLAYLISTS) == 0:
       return playlists.keys()
    else:
       return SELECTED_PLAYLISTS

def missing_report():
    with open('playlists.json','r+') as playlists_json, open('tracks.json','r+') as tracks_json:
        playlists = json.load(playlists_json)
        tracks = json.load(tracks_json)
        out = "----------------COULDNT FIND THESE ON SPOTIFY---------------<br>"
        for playlist, track_ids in playlists.items():
            if playlist not in pl_of_interest(playlists):
                continue
            out += f"PLAYLIST: {playlist}<br>"
            for tid in track_ids:
                track = tracks.get(tid, {})
                if "spotify_uri" not in track.keys():
                    out += f"     ARTIST: {track.get('artist','')}, TRACK: {track.get('name','')}<br>"
        return out

# pdb.set_trace()
if not os.path.exists("playlists.json"):
    parse_itunes('itunes.xml')
run(host='', port=8080)

