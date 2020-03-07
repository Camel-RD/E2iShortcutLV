# Install E2iStream:  
`wget --no-check-certificate http://www.softrix.co.uk/istream/installer.sh -O - | /bin/sh`  

# E2iStream plugin location:  
`/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer`  

# Configure E2iStream:  
- remove unnecessary hosts from folder (usefull hosts: hostlocalmedia, hostfavourites, ...)  
- edit files aliases.txt, list.txt in folder hosts  
- press Menu on remote, start E2iStream  
- configure buffering and caching folders  
- disable hls buffering  
  
# Install E2iShortcut files:  
- copy hostshortcutlv.py to folder hosts  
- copy shortcutlv100.png, shortcutlv120.png, shortcutlv135.png to folder icons/PlayerSelector  
- add line hostshortcutlv to list.txt in folder hosts  
- add line to aliases.txt in folder hosts  
    `"hostshortcutlv": "https://shortcut.lv/",`  
- restart enigma2
    `init 4 && sleep 10 &&  init 3`  

# Configure E2iShortcut:  
- press Menu on remote, start E2iStream  
- open All plugins and find icon for Shortcut.lv  
- press Menu on remote, select Add to group and choose User defined  
- start Shortcut plugin, press blue button, configure login, password, qualyty  
  
