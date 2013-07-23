# Copyright (C) 2013 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Request Handler for /main endpoint."""

__author__ = 'jbyeung@gmail.com (Jeff Yeung)'


import io
import jinja2
import logging
import json
import os
import webapp2
import time, threading
from datetime import datetime, tzinfo, timedelta

from google.appengine.api import memcache
from google.appengine.api import urlfetch

import httplib2
from apiclient import errors
from apiclient.http import MediaIoBaseUpload
from apiclient.http import BatchHttpRequest
from oauth2client.appengine import StorageByKeyName

from apiclient.discovery import build
from oauth2client.appengine import OAuth2Decorator


from model import Credentials
import util

from gcal import auto_refresh, get_html_from_calendar, BUNDLE_TEMPLATE_URL, EVENT_TEMPLATE_URL

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

class _BatchCallback(object):
  """Class used to track batch request responses."""

  def __init__(self):
    """Initialize a new _BatchCallbaclk object."""
    self.success = 0
    self.failure = 0

  def callback(self, request_id, response, exception):
    """Method called on each HTTP Response from a batch request.

    For more information, see
      https://developers.google.com/api-client-library/python/guide/batch
    """
    if exception is None:
      self.success += 1
    else:
      self.failure += 1
      logging.error(
          'Failed to insert item for user %s: %s', request_id, exception)


class MainHandler(webapp2.RequestHandler):
  """Request Handler for the main endpoint."""

  def _render_template(self, message=None):
    """Render the main page template."""

    userid, creds = util.load_session_credentials(self)

    template_values = {'userId': self.userid}

    if message:
      template_values['message'] = message
    
    # self.mirror_service is initialized in util.auth_required
    subscriptions = self.mirror_service.subscriptions().list().execute()
    for subscription in subscriptions.get('items', []):
      collection = subscription.get('collection')
      if collection == 'timeline':
        template_values['timelineSubscriptionExists'] = True
    
    template = jinja_environment.get_template('templates/index.html')
    self.response.out.write(template.render(template_values))

  @util.auth_required
  def get(self):
    """Render the main page."""
    # Get the flash message and delete it.
    message = memcache.get(key=self.userid)
    memcache.delete(key=self.userid)
    self._render_template(message)

  @util.auth_required
  def post(self):
    """Execute the request and render the template."""
    operation = self.request.get('operation')
    # Dict of operations to easily map keys to methods.
    operations = {
        # 'refresh': self._refresh_list,
        'send_to_glass': self._new_calendar,
    }
    if operation in operations:
      message = operations[operation]()
    else:
      message = "I don't know how to " + operation
    # Store the flash message for 5 seconds.
    memcache.set(key=self.userid, value=message, time=5)
    self.redirect('/')


  def _new_calendar(self):
    userid, creds = util.load_session_credentials(self)
    calendar_service = util.create_service("calendar", "v3", creds)
    mirror_service = util.create_service('mirror', 'v1', creds)
    
    calendar_list = calendar_service.calendarList().list().execute()
    for calendar in calendar_list['items']:
      if 'primary' in calendar:
        if calendar['primary']:
          calendar_id = calendar['id'] # grab only primary calendar      
          calendar_title = calendar['summary']
    
    #get events, only some of them
    bundle_html, event_htmls = get_html_from_calendar(calendar_service, calendar_id, calendar_title)

    body = {
            'notification': {'level': 'DEFAULT'},
            'title': calendar_title,  #stash calendar title for notify
            'text': calendar_id,      #stash calendar id for notify
            'html': bundle_html,
            'htmlPages': event_htmls,  #array
            'isBundleCover': True,
            'menuItems': [
                {
                    'action': 'CUSTOM',
                    'id': 'refresh',
                    'values': [{
                        'displayName': 'Refresh',
                        'iconUrl': util.get_full_url(self, '/static/images/refresh3.png')}]
                },
                {'action': 'TOGGLE_PINNED'},
                {'action': 'DELETE'}
            ]
        }

    try:
        result = mirror_service.timeline().insert(body=body).execute()

        item_id = result['id']
        auto_refresh(mirror_service, calendar_service, item_id, calendar_title, calendar_id, True)
                
    except errors.HttpError, error:
        logging.info ('an error has occured %s ', error)

    logging.info("new calendar insertion complete!")
    return "Calendar named \'" + calendar_title + "\'' has been added to timeline."  
  


MAIN_ROUTES = [
    ('/', MainHandler)
]
