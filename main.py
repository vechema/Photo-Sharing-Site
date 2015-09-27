import webapp2
import os
import urllib
import jinja2
import datetime

from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.ext import blobstore
from google.appengine.api import mail
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.api.images import get_serving_url


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

class Picture(ndb.Model):
    name = ndb.StringProperty()
    comments = ndb.StringProperty()
    upload_date = ndb.DateTimeProperty(auto_now_add=True)
    blob_key = ndb.BlobKeyProperty()

class Stream(ndb.Model):
    name = ndb.StringProperty()
    name_safe = ndb.StringProperty()
    creation_date = ndb.DateTimeProperty(auto_now_add=True)
    subscribers = ndb.StringProperty(repeated=True)
    tags = ndb.StringProperty(repeated=True)
    cover_url = ndb.StringProperty()
    num_pics = ndb.IntegerProperty()
    photos = ndb.StructuredProperty(Picture, repeated=True)
    view_count = ndb.IntegerProperty()

class ErrorHandler(webapp2.RequestHandler):
    def get(self):
        error_code = self.request.get('message')
        if error_code == "streamnamedup":
            message = "You tried to create a stream whose name is the same as " \
                      "an existing stream; operation did not complete"
        elif error_code == "streamnamelen":
            message = "You tried to create a stream without a name"

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

class ViewAMoreHandler(webapp2.RequestHandler):
    def get(self):
        template_values ={
        }
        template = JINJA_ENVIRONMENT.get_template('templates/viewamore.html')
        self.response.write(template.render(template_values))


class ViewAHandler(webapp2.RequestHandler):
    def get(self):
        stream_name = self.request.get('stream')

        stream_query = Stream.query(Stream.name == stream_name)
        streams = stream_query.fetch()
        stream = streams[0]

        upload_url = blobstore.create_upload_url('/upload_photo')

        photo_url_list = []
        pics = stream.photos

#        for i in range(0,3):
#            photo_url_list.append(get_serving_url(pics[i].blob_key))

        template_values = {
            'stream' : stream,
            'upload_url' : upload_url,
            'photo_url_list' : photo_url_list,
        }
        template = JINJA_ENVIRONMENT.get_template('templates/viewa.html')
        self.response.write(template.render(template_values))


class PhotoUploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        try:
            #Get the blob_key
            upload = self.get_uploads()[0]

            #Get name & comments
            photo_name = self.request.get('filename')
            photo_comment = self.request.get('comment')

            user_photo = Picture(blob_key=upload.key(), name=photo_name, comments=photo_comment)
            user_photo.put()
            self.redirect('/')
        except:
            self.error(500)

class CreateHandler(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return
        template_values ={
        }
        template = JINJA_ENVIRONMENT.get_template('templates/create.html')
        self.response.write(template.render(template_values))

    def post(self):
        #Get the name of the stream
        stream_name = self.request.get('streamname')
        if len(stream_name) == 0:
            self.redirect('/error?message=streamnamelen')
            return
        #Need to see if a stream with that name already exists
        stream_query = Stream.query(Stream.name == stream_name)
        streams = stream_query.fetch(400)
        if streams:
            self.redirect('/error?message=streamnamedup')
            return

        #get the emails and then send 'em
        emails = self.request.get('subscribers').split(",")
        email_message = self.request.get('message')
        #Need to change this to the actual url of the stream
        stream_url = "http://apt2015mini.appspot.com/view?stream=" + urllib.quote_plus(stream_name)
        sendSubscriptionEmails(emails, email_message, stream_url)

        #tags
        tag_list = self.request.get('tags').replace('#', '').split(" ")

        #cover image
        cover = self.request.get('coverurl')
        if(len(cover) == 0):
            cover = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/No_image_available.svg/300px-No_image_available.svg.png"

        #Put it all together in a stream object
        safe_name_url = urllib.quote_plus(stream_name)
        stream = Stream(name=stream_name, name_safe=safe_name_url, subscribers=emails, tags=tag_list, cover_url=cover)
        stream.put()

        self.redirect('/manage')

def sendSubscriptionEmails(emails, note, stream_url):
    user = users.get_current_user()
    for email in emails:
        if len(email) > 0:
            message = mail.EmailMessage(sender=user.email(),
                                    subject="You were subscribed")

            message.to = email
            message.body = note + """

            This message was sent by """ + stream_url

            message.send()

class ManageHandler(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return
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
        if user:
            name = user.nickname()
            url = users.create_logout_url('/login')
            url_linktext = "Logout"
        else:
            name = "stranger"
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
    ('/viewmore', ViewAMoreHandler),
    ('/upload_photo', PhotoUploadHandler),
    ('/view', ViewAHandler),
    ('/create', CreateHandler),
    ('/manage', ManageHandler),
    ('/login', LoginHandler),
    ('/', MainPage),
    ('/purge', PurgeHandler),
    ], debug=True)