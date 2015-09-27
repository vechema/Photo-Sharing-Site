import webapp2
import os
import urllib
import jinja2
import datetime
import cgi

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
    comment = ndb.StringProperty()
    upload_date = ndb.DateTimeProperty(auto_now_add=True)
    blob_key = ndb.BlobKeyProperty()
    pic_url = ndb.StringProperty()


class Stream(ndb.Model):
    name = ndb.StringProperty()
    name_safe = ndb.StringProperty()
    creation_date = ndb.DateTimeProperty(auto_now_add=True)
    subscribers = ndb.StringProperty(repeated=True)
    tags = ndb.StringProperty(repeated=True)
    cover_url = ndb.StringProperty()
    photos = ndb.StructuredProperty(Picture, repeated=True)
    view_count = ndb.DateTimeProperty(repeated=True)
    count = ndb.ComputedProperty(lambda e: len(e.view_count))

class Leaders(ndb.Model):
    name = ndb.StringProperty()
    leader1 = ndb.StructuredProperty(Stream)
    leader2 = ndb.StructuredProperty(Stream)
    leader3 = ndb.StructuredProperty(Stream)

class MyUser(ndb.Model):
    streams_own = ndb.StringProperty(repeated=True) #Going to hold stream names
    streams_subscribe = ndb.StringProperty(repeated=True) #Going to hold stream names
    email = ndb.StringProperty()
    update_rate = ndb.StringProperty()


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

        #add the current date and time to the stream's view_count list
        views = stream.view_count
        now = datetime.datetime.now()
        views.append(now)
        hourback = now - datetime.timedelta(hours = 1)
        self.response.write(hourback)

        for view in views:
            if view<hourback:
                views.remove(view)

        stream.view_count = views

        stream.put()




        upload_url = blobstore.create_upload_url('/upload_photo')

        photo_url_list = []
        pics = stream.photos
        limit = len(pics)
        if limit > 3:
            limit = 3

        for i in range(0,limit):
            photo_url_list.append(get_serving_url(pics[i].blob_key))

        template_values = {
            'stream' : stream,
            'upload_url' : upload_url,
            'photo_url_list' : photo_url_list,
        }
        template = JINJA_ENVIRONMENT.get_template('templates/viewa.html')
        self.response.write(template.render(template_values))
        for view in views:
            self.response.write(str(view) + '<br>')


class PhotoUploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        try:
            #Get the blob_key
            upload = self.get_uploads()[0]

            garbage = self.get_uploads()

            #Get stream, name & comments
            photo_name = self.request.get('file_name')
            photo_comment = self.request.get('comment')
            stream_name = self.request.get('stream')

            # name = self.request.get('stream')
            # stream_query = Stream.query(Stream.name == stream_name)
            # streams = stream_query.fetch()
            # stream = streams[0]

            user_photo = Picture(blob_key=upload.key(), name=photo_name, comment=photo_comment)
            img_url = get_serving_url(user_photo.blob_key)
            user_photo.pic_url = img_url
            user_photo.put()
            self.redirect('/' + stream_name)
        except:
            self.error(500)


class AllPhotosHandler(webapp2.RequestHandler):
    def get(self):

        photo_query = Picture.query().order(-Picture.upload_date)
        photos = photo_query.fetch()
        # i = 0
        # pic_url_list = []
        # for result in photos:
        #     i = i + 1
        #     photo_key = result.blob_key
        #     img_url = get_serving_url(photo_key)
        #     pic_url_list.append(img_url)

        template_values = {
#            'pic_url_list' : pic_url_list,
            'photos' : photos,
        }
        template = JINJA_ENVIRONMENT.get_template('templates/allpics.html')
        self.response.write(template.render(template_values))

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
        stream = Stream()
        stream.name=stream_name
        stream.name_safe=safe_name_url
        stream.subscribers=emails
        stream.tags=tag_list
        stream.cover_url=cover

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
            stream_message = (str(index) + ' items deleted from Stream at ' + str(hour) + ':' + str(minute) + ':' + str(second)+'\n\n')
            if index == 400:
                self.redirect("/purge")


        except Exception, e:
 #           self.response.out.write('Error is: ' + repr(e) + '\n')
            pass

        try:
            stream_query = Picture.query()
            streams = stream_query.fetch(400)
            index = 0
            if len(streams) > 0:
                for result in streams:
                    result.key.delete()
                    index+=1

            hour = datetime.datetime.now().time().hour
            minute = datetime.datetime.now().time().minute
            second = datetime.datetime.now().time().second
            pic_message = (str(index) + ' items deleted from Picture at ' + str(hour) + ':' + str(minute) + ':' + str(second)+'\n\n')
            if index == 400:
                self.redirect("/purge")


        except Exception, e:
 #           self.response.out.write('Error is: ' + repr(e) + '\n')
            pass
        template_values ={
            'blob_message' : blob_message,
            'stream_message' : stream_message,
            'pic_message' : pic_message,
        }
        template = JINJA_ENVIRONMENT.get_template('templates/purge.html')
        self.response.write(template.render(template_values))


class TrendingHandler(webapp2.RequestHandler):
    def get(self):
        template_values = {}
        template = JINJA_ENVIRONMENT.get_template('templates/trends.html')
        self.response.write(template.render(template_values))


        #find the leaders and store them in the database
        stream_query = Stream.query().order(Stream.count)
        streams = stream_query.fetch(3)
        leads = Leaders(name = 'champions', leader1 = streams[0], leader2 = streams[1], leader3 = streams[2])
        leads.put()

        #gets the leaders from the datastore
        leads_query = Leaders.query(Leaders.name == 'champions')
        leads = leads_query.fetch()
        lead = leads[0]

        #prints the leaders
        self.response.write(lead.leader1.name)
        self.response.write(lead.leader2.name)
        self.response.write(lead.leader3.name)

class UpdateHandler(webapp2.RequestHandler):
    def get(self):
        stream_query = Stream.query().order(len(Stream.view_count))
        streams = stream_query.fetch(3)
        leads = Leaders(name = 'champions', leader1 = streams[0], leader2 = streams[1], leader3 = streams[2])
        leads.put()


app = webapp2.WSGIApplication([
    ('/allpics', AllPhotosHandler),
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
    ('/trending', TrendingHandler),
    ('/update', UpdateHandler),
    ], debug=True)