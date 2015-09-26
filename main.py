import webapp2
import os
import urllib
import jinja2
import datetime

from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.ext import blobstore
from google.appengine.api.images import get_serving_url


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

class Stream(ndb.Model):
    name = ndb.StringProperty()
    creation_date = ndb.DateTimeProperty(auto_now_add=True)
    subscribers = ndb.StringProperty(repeated=True)

class ErrorHandler(webapp2.RequestHandler):
    def get(self):
        error_code = self.request.get('message')
        
        template_values ={
            'message' : message
        }
        template = JINJA_ENVIRONMENT.get_template('templates/error.html')
        self.response.write(template.render(template_values))

class ViewAllHandler(webapp2.RequestHandler):
    def get(self):
        stream_names = []
        stream_query = Stream.query().order(-Stream.creation_date)
        streams = stream_query.fetch(400)

        template_values ={
            'streams' : streams
        }
        template = JINJA_ENVIRONMENT.get_template('templates/viewall.html')
        self.response.write(template.render(template_values))

class CreateHandler(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
        else:
            template_values ={
            }
            template = JINJA_ENVIRONMENT.get_template('templates/create.html')
            self.response.write(template.render(template_values))

    def post(self):
        stream_name = self.request.get('streamname')
        #Need to see if a stream with that name already exists
        stream_query = Stream.query()#Stream.name == stream_name)
        streams = stream_query.fetch(400)
        if not streams:
            emails = self.request.get('subscribers').split(",")
            stream = Stream(name=stream_name, subscribers=emails)
            stream.put()
            self.redirect('/manage')
        else:
            self.redirect('/error?message=streamname')

class ManageHandler(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
        else:
            name = user.nickname()
            template_values ={
                'name' : name,
            }
            template = JINJA_ENVIRONMENT.get_template('templates/manage.html')
            self.response.write(template.render(template_values))

class MainPage(webapp2.RequestHandler):
    def get(self):
        self.redirect('/manage')

class LoginHandler(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        name = "stranger"
        if user:
            name = user.nickname()
            url = users.create_logout_url('/login')
            url_linktext = "Logout"
        else:
            url = users.create_login_url('/')
            url_linktext = "Login"

        greeting = "Howdy, " + name

        template_values = {
            'user': user,
            'greeting': greeting,
            'url' : url,
            'url_linktext' : url_linktext,
        }

        template = JINJA_ENVIRONMENT.get_template('templates/login.html')
        self.response.write(template.render(template_values))

class PurgeHandler(webapp2.RequestHandler):
    def get(self):

        try:
            query = blobstore.BlobInfo.all()
            blobs = query.fetch(400)
            index = 0
            if len(blobs) > 0:
                for blob in blobs:
                    blob.delete()
                    index += 1

            hour = datetime.datetime.now().time().hour
            minute = datetime.datetime.now().time().minute
            second = datetime.datetime.now().time().second
            blob_message = (str(index) + ' items deleted from Blobstore at ' + str(hour) + ':' + str(minute) + ':' + str(second)+'\n\n')
            if index == 400:
                self.redirect("/purge")

        except Exception, e:
#            self.response.out.write('Error is: ' + repr(e) + '\n')
            pass

        try:
            stream_query = Stream.query()
            streams = stream_query.fetch(400)
            index = 0
            if len(streams) > 0:
                for result in streams:
                    result.key.delete()
                    index+=1

            hour = datetime.datetime.now().time().hour
            minute = datetime.datetime.now().time().minute
            second = datetime.datetime.now().time().second
            data_message = (str(index) + ' items deleted from Datastore at ' + str(hour) + ':' + str(minute) + ':' + str(second)+'\n\n')
            if index == 400:
                self.redirect("/purge")


        except Exception, e:
 #           self.response.out.write('Error is: ' + repr(e) + '\n')
            pass
        template_values ={
            'blob_message' : blob_message,
            'data_message' : data_message,
        }
        template = JINJA_ENVIRONMENT.get_template('templates/purge.html')
        self.response.write(template.render(template_values))

app = webapp2.WSGIApplication([
    ('/error', ErrorHandler),
    ('/viewall', ViewAllHandler),
    ('/create', CreateHandler),
    ('/manage', ManageHandler),
    ('/login', LoginHandler),
    ('/', MainPage),
    ('/purge', PurgeHandler),
    ], debug=True)