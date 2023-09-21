# Hover Ploogin 0.42
# Ploogs into your Sublime and generates tooltips for localization keys and modifiers
# Probably buggy but tries very hard

# New in 0.42:
# looks at a lot more folders, might be too slow for big projects (?)
# New in 0.41: 
# scripted_effects and script_values now also have tooltips with links to their source
# the blue link is now at the top of the tooltip instead of the bottom, because some effects are looong

"""
# Instructions

As of 0.20, you have to set your working game directory manually to ensure that the ploogin always knows where to look.

Open your Sublime settings (Preferences ➝ Settings) and add the following line to your User settings file (opened on the right):
	"pdx_game_path": "C:\\path\\to\\your\\game\\directory"
Replace the path with the path to your "game" folder. Replace any backslashes (\) with double backslashes (\\).
Remember that every line in the Settings file except for the last one should end with a comma.
Restart Sublime after setting the path in your settings.

If you are working on Crusader Kings II or another script file-heavy game, you may experience slowdowns when using the ploogin.
To avoid this, add this additional line to the User settings file:
	"pdx_do_not_scan_script": true
This prevents the ploogin from scanning all text files in your game directory for localization key references and stops the slowdowns.

If you are using the new event syntax where the ID is printed in front of the first curly bracket instead of inside the event scope (Titus and Caligula), add the following to your User settings file:
	"pdx_new_event_style": true

"""

import sublime
import sublime_plugin
import os
import re

locDict = {}
reverseLocDict = {}
modifierDict = {}
eventDict = {}

def plugin_loaded():
	sublime.set_timeout_async(loadFilesAsync, 0)

def loadFilesAsync():
	gamepath = sublime.active_window().active_view().settings().get('pdx_game_path')
	if not gamepath:
		sublime.error_message('hoverPloogin: Game path not found.\nPlease set "pdx_game_path" in your Sublime settings to the game folder you are working from.')
		return
	locpath = ""
	if os.path.isdir(os.path.join(gamepath, 'localisation')):
		locpath = os.path.join(gamepath, 'localisation')
	elif os.path.isdir(os.path.join(gamepath, 'localization')):
		locpath = os.path.join(gamepath, 'localization')
	if locpath:
		for dirpath, subs, files in os.walk(locpath):
			for f in files:
				if '_l_english' in f and '.yml' in f:
					p = open(os.path.join(dirpath, f), 'U', encoding="utf-8")
					lines = p.readlines()
					p.close()
					for nr, line in enumerate(lines[1:]):
						if not line.strip().startswith('#') and ':' in line:
							key = line[:line.find(':')].strip()
							value = buildLocTooltip(line[line.find('"'):], os.path.join(dirpath, f), str(nr+2))
							locDict[key] = value
				if '.csv' in f:
					p = open(os.path.join(dirpath, f), encoding="windows-1252", errors='replace')
					lines = p.readlines()
					p.close()
					for nr, line in enumerate(lines[1:]):
						if not line.strip().startswith('#') and ';' in line:
							key = line.split(';')[0]
							value = buildLocTooltip(line.split(';')[1], os.path.join(dirpath, f), str(nr+2))
							locDict[key] = value
		print('Localization loaded from: ' + locpath)
	else:
		print('Localization folder not found.')

	# Find the common folder
	commonpath = os.path.join(gamepath, 'common')
	if os.path.isdir(commonpath):
		print('Common directory found at: ' + commonpath)
		# Load modifier files
		for dirpath, subs, files in os.walk(commonpath):
			for file in files:
				path = os.path.join(dirpath, file)
				if 'modifier' in path:
					f = open(path, 'U')
					lines = f.readlines()
					f.close()
					readModifiers(lines, path)
		print(str(len(modifierDict)) + ' modifiers Loaded.')
		# Load scripted triggers and effects
		for dirpath, subs, files in os.walk(commonpath):
			for file in files:
				path = os.path.join(dirpath, file)
				if 'scripted_triggers' in path or 'scripted_effects' in path or 'script_values' in path:
					f = open(path, 'U')
					lines = f.readlines()
					f.close()
					readModifiers(lines, path)
		# print(str(len(modifierDict)) + ' script values, scripted triggers and effects loaded.')

	else:
		print('Common directory not found.')

	# Find the event folder
	eventpath = os.path.join(gamepath, 'events')
	if os.path.isdir(eventpath):
		print('Event directory found at: ' + eventpath)
		# Load modifier files
		for dirpath, subs, files in os.walk(eventpath):
			for file in files:
				path = os.path.join(dirpath, file)
				f = open(path, encoding="UTF-8")
				lines = f.readlines()
				f.close()
				readEvents(lines, path)
		print(str(len(eventDict)) + ' events Loaded.')
	else:
		print('Event directory not found.')

	# Read all script files from game folder.
	# Load all text files
	if not sublime.active_window().active_view().settings().get('pdx_do_not_scan_script'):
		for dirpath, subs, files in os.walk(gamepath):
			for file in files:
				if file.endswith('.txt') or file.endswith('.gui'):
					path = os.path.join(dirpath, file)
					f = open(path, 'U', errors='replace')
					lines = f.readlines()
					buildReverseLoc(lines, path)
					readModifiers(lines, path)
					f.close()
		print('Script files scanned for localization references.')
		print('Even more ' + str(len(modifierDict)) + ' script values, scripted triggers and effects loaded.')
	else:
		print('Script files not scanned for localization references as per "pdx_do_not_scan_script" setting.')

	print('Finished loading Paradox game data.')

def buildLocTooltip(value, filename, line):
	#return value.replace('\\n', '<br>') + '<br><a href="' + filename + ':' + line + '">Goto➝</a>'
	return '<a href="' + filename + ':' + line + '" style="font-style:italic;text-decoration:none;">' + os.path.split(filename)[-1] + '</a><br>' + value.replace('\\n', '<br>')

def readModifiers(lines, filename):
	# Does the bare minimum to separate modifiers (and scripted triggers/effects) and put them in a dictionary
	# A good way to get snippets, not to parse the structure
	curlyboys = 0
	currentModifier = None
	modLineCache = []
	for nr, line in enumerate(lines):
		# Remove Byte Order Mark
		line = line.replace('ï»¿', '')
		# Remove comments
		if '#' in line:
			cleanLine = line[:line.find('#')]
		else:
			cleanLine = line
		if curlyboys:
			modLineCache.append(line)
			if '{' in cleanLine:
				curlyboys += cleanLine.count('{')
			if '}' in cleanLine:
				curlyboys -= cleanLine.count('}')
			if curlyboys == 0:
				modifierDict[currentModifier] = buildModifierTooltip(modLineCache[2:], modLineCache[0], modLineCache[1])
		else:
			if '{' or '=' in cleanLine:
				currentModifier = cleanLine.split('=')[0].strip()
				curlyboys += cleanLine.count('{')
				curlyboys -= cleanLine.count('}')
				modLineCache = [filename, str(nr+1), line]
				# Check if modifier wraps up in one line
				if not curlyboys:
					modifierDict[currentModifier] = buildModifierTooltip(modLineCache[2:], modLineCache[0], modLineCache[1])

def readEvents(lines, filename):
	# Reuses the general principle for detecting base scope from modifiers function
	curlyboys = 0
	for nr, line in enumerate(lines):
		# Remove Byte Order Mark
		line = line.replace('ï»¿', '')
		# Remove comments
		if '#' in line:
			cleanLine = line[:line.find('#')]
		else:
			cleanLine = line
		if curlyboys:
			if '{' in cleanLine:
				curlyboys += cleanLine.count('{')
			if '}' in cleanLine:
				curlyboys -= cleanLine.count('}')
			if curlyboys == 1 and not sublime.active_window().active_view().settings().get('pdx_new_event_style'):
				if cleanLine.split('=')[0].strip() == 'id' and len(cleanLine.split('=')) == 2:
					eventID = cleanLine.split('=')[1].strip()
					eventDict[eventID] = buildEventTooltip(eventID, filename, str(nr+1))
		else:
			if '{' in cleanLine:
				# Set event if new style
				if sublime.active_window().active_view().settings().get('pdx_new_event_style'):
					if len(cleanLine.split('=')) == 2 and cleanLine.split('=')[1].strip() == '{':
						eventID = cleanLine.split('=')[0].strip()
						eventDict[eventID] = buildEventTooltip(eventID, filename, str(nr+1))
				curlyboys += cleanLine.count('{')
				curlyboys -= cleanLine.count('}')
				# Check if event wraps up in one line (why would you do that, WHY?)
				if not curlyboys:
					pass



def buildModifierTooltip(lines, filename, line):
	return '<a href="' + filename + ':' + line + '" style="font-style:italic;text-decoration:none;">' + os.path.split(filename)[-1] + '</a><br>' + ''.join(lines).replace('\n', '<br>').replace('\t', '&nbsp;&nbsp;') 

def buildEventTooltip(eventID, filename, line):
	return '<a href="' + filename + ':' + line + '" style="font-style:italic;text-decoration:none;">' + os.path.split(filename)[-1] + '</a><br>' + eventID

def buildReverseLoc(lines, filename):
	for nr, line in enumerate(lines):
		words = re.split("[\"'+={}:\s#]", line)
		# if filename == '00_regions.txt': print(line)
		for word in words:
			if word in locDict:
				if word not in reverseLocDict:
					reverseLocDict[word] = ""
				reverseLocDict[word] += buildReverseLocTooltip(line, filename, str(nr+1))

def buildReverseLocTooltip(value, filename, line):
	return '<a href="' + filename + ':' + line + '" style="font-style:italic;text-decoration:none;">' + os.path.split(filename)[-1] + '</a>' + '<br>' + value

class GetLocalizationOnHover(sublime_plugin.EventListener):
	def on_hover(self, view, point, hover_zone):
		hoverWord = view.expand_by_class(point, sublime.CLASS_WORD_START + sublime.CLASS_WORD_END, "\"'+={}:\n#")
		hoverString = view.substr(hoverWord)
		# print(hoverString)
		if view.file_name():
			if view.file_name().endswith('.yml') or view.file_name().endswith('.csv'):
				if hoverString in reverseLocDict:
					view.show_popup(reverseLocDict[hoverString], sublime.HIDE_ON_MOUSE_MOVE_AWAY, point, 800, 800, self.open_loc_to_line)
				elif hoverString in locDict:
					view.show_popup("No references found.", sublime.HIDE_ON_MOUSE_MOVE_AWAY, point)
			elif hoverString in modifierDict and hoverString in locDict:
				view.show_popup(modifierDict[hoverString] + '<br>' + locDict[hoverString], sublime.HIDE_ON_MOUSE_MOVE_AWAY, point, 800, 800, self.open_loc_to_line, self.remove_highlight)
				view.add_regions('hover_region', [hoverWord], "meta.annotation", flags=sublime.DRAW_NO_FILL)
			elif hoverString in modifierDict:
				view.show_popup(modifierDict[hoverString], sublime.HIDE_ON_MOUSE_MOVE_AWAY, point, 800, 800, self.open_loc_to_line, self.remove_highlight)
				view.add_regions('hover_region', [hoverWord], "meta.annotation", flags=sublime.DRAW_NO_FILL)
			elif hoverString in eventDict:
				view.show_popup(eventDict[hoverString], sublime.HIDE_ON_MOUSE_MOVE_AWAY, point, 800, 800, self.open_loc_to_line, self.remove_highlight)
				view.add_regions('hover_region', [hoverWord], "meta.annotation", flags=sublime.DRAW_NO_FILL)
			elif hoverString in locDict:
				view.show_popup(locDict[hoverString], sublime.HIDE_ON_MOUSE_MOVE_AWAY, point, 800, 800, self.open_loc_to_line, self.remove_highlight)
				view.add_regions('hover_region', [hoverWord], "meta.annotation", flags=sublime.DRAW_NO_FILL)
			#elif hoverString + '_desc' in locDict:
			#	view.show_popup(locDict[hoverString + '_desc'], sublime.HIDE_ON_MOUSE_MOVE_AWAY, point, 800, 800)

	def open_loc_to_line(self, fileline):
		sublime.active_window().open_file(fileline, sublime.ENCODED_POSITION)

	def remove_highlight(self):
		sublime.active_window().active_view().erase_regions('hover_region')
		
	def on_post_save(self, view):
		# Localization files (YML or CSV in any folder)
		if '.yml' in view.file_name():
			lines = view.substr(sublime.Region(0, view.size())).split('\n')
			for nr, line in enumerate(lines[1:]):
				if not line.strip().startswith('#') and ':' in line:
					key = line[:line.find(':')].strip()
					value = buildLocTooltip(line[line.find('"'):], view.file_name(), str(nr+2))
					locDict[key] = value
		elif '.csv' in view.file_name():
			lines = view.substr(sublime.Region(0, view.size())).split('\n')
			for nr, line in enumerate(lines[1:]):
				if not line.strip().startswith('#') and ';' in line:
					key = line.split(';')[0]
					value = buildLocTooltip(line.split(';')[1], view.file_name(), str(nr+2))
					locDict[key] = value
		elif 'txt' in view.file_name() and 'modifier' in view.file_name():
			lines = view.substr(sublime.Region(0, view.size())).splitlines(keepends=True)
			readModifiers(lines, view.file_name())
