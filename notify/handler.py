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
# WITHOUT WARRANTIES OR CsecreONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Request Handler for /notify endpoint."""

# need to configure the methods to handle menu actions from oauth for tasks
# leave at marking complete only, no uncompleting
# also voice command to make new task


__author__ = 'jbyeung@gmail.com (Jeff Yeung)'


import io
import json
import logging
import webapp2

from apiclient.http import MediaIoBaseUpload
from apiclient import errors
from oauth2client.appengine import StorageByKeyName

from model import Credentials
import util

from gcal import refresh_me


class NotifyHandler(webapp2.RequestHandler):
  """Request Handler for notification pings."""

  def post(self):
    """Handles notification pings."""
    logging.info('Got a notification with payload %s', self.request.body)
    data = json.loads(self.request.body)
    userid = data['userToken']
    # TODO: Check that the userToken is a valid userToken.
    self.mirror_service = util.create_service(
        'mirror', 'v1',
        StorageByKeyName(Credentials, userid, 'credentials').get())
    self.calendar_service = util.create_service(
        'calendar', 'v3', 
        StorageByKeyName(Credentials, userid, 'credentials').get())
    if data.get('collection') == 'timeline':
      self._handle_timeline_notification(data)


  def _handle_timeline_notification(self, data):
    """Handle timeline notification."""
    
    
    item_id = data.get('itemId')
    userid = data.get('userToken')

    #process actions
    logging.info('timeline notification received')
    logging.info(userid)
    
    #for user_action in data.get('userActions', []):
    if data.get('userActions', [])[0]:
        user_action = data.get('userActions', [])[0]
        logging.info(user_action)
        payload = user_action.get('payload')

        if user_action.get('type') == 'CUSTOM' and payload == 'refresh':
            # create local vars for selected tasklist

            timeline_item = self.mirror_service.timeline().get(id=item_id).execute()
            calendar_list = self.calendar_service.calendarList().list().execute()
            for calendar in calendar_list['items']:
                if 'primary' in calendar:
                    if calendar['primary']:
                        calendar_id = calendar['id'] # grab only primary calendar      
                        calendar_title = calendar['summary']

            refresh_me(self.mirror_service, self.calendar_service, item_id, calendar_title, calendar_id)


NOTIFY_ROUTES = [
    ('/notify', NotifyHandler)
]

