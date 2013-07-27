#calendar functions

import os
import jinja2
import logging
from apiclient import errors

import time, threading
from datetime import datetime, timedelta
from google.appengine.ext import deferred

import util

BUNDLE_TEMPLATE_URL = 'templates/bundle.html'
EVENT_TEMPLATE_URL = 'templates/event.html'

DEFAULT_REFRESH_TIME = 3600.0     #auto-refresh every hour

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

def auto_refresh(creds, mirror_service, calendar_service, item_id, calendar_title, calendar_id, first_time=None):
	#check if calendar and timeline item still exist
	#then refresh, set a timer to refresh again on new thread

	logging.info('auto refresh called')

	calendar_service = util.create_service('calendar', 'v3', creds)
	mirror_service = util.create_service('mirror', 'v1', creds)

	try:
	  timeline_item = mirror_service.timeline().get(id = item_id).execute()
	  calendar_item = calendar_service.calendarList().get(calendarId = calendar_id).execute()
	  if timeline_item.get('isDeleted') or not calendar_item:
	  	logging.info("stopped auto-refresh")
	  	return "auto-refresh halted, timeline item or calendar does not exist"

	except errors.HttpError, error:
	  logging.info("error in auto-refresh try")
	  return "auto-refresh error, breaking"

	if not first_time:
		refresh_me(mirror_service, calendar_service, item_id, calendar_title, calendar_id)  

	time.sleep(DEFAULT_REFRESH_TIME)
	logging.info('about to start new thread')
	deferred.defer(auto_refresh, creds, mirror_service, calendar_service, item_id, calendar_title, calendar_id)
	logging.info('new thread started')
	return "auto-refresh thread done"
	
def refresh_me(mirror_service, calendar_service, item_id, calendar_title, calendar_id):

	logging.info('refresh me called')

	bundle_html, event_htmls = get_html_from_calendar(calendar_service, calendar_id, calendar_title)

	patched_timeline_item = {'html': bundle_html, 
	                        'htmlPages': event_htmls}

	try:
	    result = mirror_service.timeline().patch(id=item_id, body=patched_timeline_item).execute()
	except errors.HttpError, error:
	    logging.info ('an error has occured %s ', error)
	return "Calendar named \'" + calendar_title + "\'' has been refreshed."  

    
def get_html_from_calendar(calendar_service, calendar_id, calendar_title):
    my_events = []
    event_htmls = []
    template_values = {}
    MAX_EVENTS = 10
    
    logging.info('beginning to grab events')

    page_token = None
    
    dt_utc = datetime.utcnow()
    dt_local = dt_utc - timedelta(seconds=time.altzone)
    timeMin = dt_local.isoformat("T") + "Z"
    
    logging.info("min")
    logging.info(timeMin)
    events = calendar_service.events().list(calendarId=calendar_id, 
                                            pageToken=page_token, 
                                            singleEvents=True, 
                                            orderBy="startTime", 
                                            timeMin=timeMin, 
                                            maxResults=MAX_EVENTS).execute()
    if events:
	    for event in events['items']:
	      #parse these
	      logging.info("start")
	      logging.info(event['start'])
	      e = {}
	      
	      if 'start' in event: 
	        if 'dateTime' in event['start']:
	          e['startDate'] = event['start']['dateTime'][0:10]
	          e['startTime'] = event['start']['dateTime'][11:16]

	          d = datetime.strptime(e['startTime'], '%H:%M')
	          e['startTime'] = d.strftime('%I:%M')
	        else:
	          
	          e['startDate'] = event['start']['date']
	          e['startTime'] = ''   
	        d = datetime.strptime(e['startDate'], '%Y-%m-%d')
	        e['startDate'] = d.strftime('%a, %b %d')
	        
	      if 'end' in event: 
	        if 'dateTime' in event['end']:
	          e['endDate'] = event['end']['dateTime'][0:10]
	          e['endTime'] = event['end']['dateTime'][11:16]
	          d = datetime.strptime(e['endTime'], '%H:%M')
	          e['endTime'] = d.strftime('%I:%M%p')
	        else:
	          e['endDate'] = event['end']['date']
	          e['endTime'] = ''
	        d = datetime.strptime(e['endDate'], '%Y-%m-%d')
	        e['endDate'] = d.strftime('%a, %b %d')
	        
	      if 'summary' in event: 
	        e['title'] = event['summary']
	      if 'description' in event: 
	        e['description'] = event['description']
	      if 'location' in event: 
	        e['location'] = event['location']
	      if 'reminder' in event: 
	        e['reminder'] = event['reminders']
	     

	      my_events.append(e)

	      #set html for individual events
	      template_values['event'] = e
	      template = jinja_environment.get_template(EVENT_TEMPLATE_URL)
	      html = template.render(template_values)
	      event_htmls.append(html)

	    logging.info('done grabbing events')

	    #############
	    #now build the bundle to push to timeline
	    
	    template = jinja_environment.get_template(BUNDLE_TEMPLATE_URL)
	    template_values['events'] = my_events
	    template_values['calendar_title'] = calendar_title


	    bundle_html = template.render(template_values)
	    
	    return bundle_html, event_htmls

