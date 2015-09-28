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
    champs = ndb.KeyProperty(repeated=True)

class MyUser(ndb.Model):
    streams_own = ndb.KeyProperty(repeated=True) #Going to hold stream names
    streams_subscribe = ndb.KeyProperty(repeated=True) #Going to hold stream keys
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

        #add the current date and time to the stream's view_count list if viewer is not stream owner
        views = stream.view_count
        now = datetime.datetime.now()

        #Check that the user is not the one viewing the stream
        #If the user is not signed in, it counts as a view
        user = users.get_current_user()
        if not user:
            views.append(now)
        #If the user is signed it, check that this is not one of their streams
        else:
            userkey = ndb.Key(MyUser, user.email())

            #confirm or create MyUser object
            if (userkey.get() == None):
                NewUser = MyUser(id = user.email(), email = user.email(),update_rate = 'never')
                NewUser.put()

            currentuser = userkey.get()

            #Is user's stream keys do not contain this stream key, add view to stream's view queue
            if (stream.key not in currentuser.streams_own):
                views.append(now)

        #Purge hour old views
        hourback = now - datetime.timedelta(hours = 1)
        #self.response.write(hourback)

        for view in views:
            if view<hourback:
                views.remove(view)

        stream.view_count = views

        stream.put()




        upload_url = blobstore.create_upload_url('/upload_photo')

        photo_url_list = []
        pics = stream.photos
        hard_limit = 3
        limit = len(pics)
        if limit > hard_limit:
            limit = hard_limit

        for i in range(0,limit):
            photo_url_list.append(get_serving_url(pics[i].blob_key))

        template_values = {
            'stream' : stream,
            'upload_url' : upload_url,
            'photo_url_list' : photo_url_list,
        }
        template = JINJA_ENVIRONMENT.get_template('templates/viewa.html')
        self.response.write(template.render(template_values))
        self.response.write(stream.count)
        # for view in views:
        #     self.response.write(str(view) + '<br>')


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

            #Add the picture to it's stream
            stream_query = Stream.query(Stream.name == stream_name)
            streams = stream_query.fetch()
            stream = streams[0]

            list_pics = stream.photos
            list_pics.insert(0, user_photo)
            #list_pics.append(user_photo)
            stream.photos = list_pics
            #stream.photos.append(user_photo)
            #stream.photos[0] = user_photo
            stream.put()

            self.redirect('/view?stream=' + stream_name)
            #self.redirect('/')
        except:
            self.error(500)


class AllPhotosHandler(webapp2.RequestHandler):
    def get(self):

        photo_query = Picture.query().order(-Picture.upload_date)
        photos = photo_query.fetch()

        template_values = {
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

        #confirm or create MyUser object
        #MyUser instances are stored in blobstore using the user email as a key (id)
        userkey = ndb.Key(MyUser, user.email())

        if (userkey.get() == None):
            NewUser = MyUser(id = user.email(), email = user.email(),update_rate = 'never')
            NewUser.put()

        # ThisUser = userkey.get()
        # self.response.write(ThisUser.email)
        # self.response.write(ThisUser.update_rate)

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
        #Find current update rate
        #Check to make sure there is a user object
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return

        #confirm or create MyUser object
        userkey = ndb.Key(MyUser, user.email())

        if (userkey.get() == None):
            NewUser = MyUser(id = user.email(), email = user.email(),update_rate = 'never')
            NewUser.put()

        currentrate = userkey.get().update_rate


        #set already known key for leader information
        thekey = ndb.Key(Leaders, 'lkey')

        #check to see if leader information is available yet
        if(thekey.get()==None):
            return

        #GETS THE LEADERS FROM THE DATASTORE
        leads_retrieved = thekey.get()

        #testing
        # self.response.write(leads_retrieved.key)

        leaders = []

        # prints the leaders
        for champ in leads_retrieved.champs:
            leaders.append(champ.get())


        template_values ={
            'current_rate' : currentrate,
            'streams' : leaders,
        }
        template = JINJA_ENVIRONMENT.get_template('templates/trends.html')
        self.response.write(template.render(template_values))

    def post(self):
        #Get the rate choice
        rate_choice = self.request.get('rate')

        #Check to make sure there is a user object
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return

        #confirm or create MyUser object
        #MyUser instances are stored in blobstore using the user email as a key (id)
        userkey = ndb.Key(MyUser, user.email())

        if (userkey.get() == None):
            NewUser = MyUser(id = user.email(), email = user.email(),update_rate = 'never')
            NewUser.put()

        #update rate of currentuser
        current_user = userkey.get()
        current_user.update_rate = rate_choice
        current_user.put()

        # self.response.write(current_user.update_rate)
        self.redirect('/trending')


class UpdateHandler(webapp2.RequestHandler):
    def get(self):
        #purge all views over an hour old
        allstreams = Stream.query()
        for eachstream in allstreams:
            views = eachstream.view_count
            now = datetime.datetime.now()

            hourback = now - datetime.timedelta(hours = 1)


            for view in views:
                if view<hourback:
                    views.remove(view)

            eachstream.view_count = views

            eachstream.put()


        #find the leaders
        stream_query = Stream.query().order(-Stream.count)
        streams = stream_query.fetch(3)


        #Store them by key in the database in a leader's object
        leads_stored = Leaders(id = 'lkey')
        for stream in streams:
            leads_stored.champs.append(stream.key)
        leaderkey = leads_stored.put()

        # self.response.write(leaderkey)

class SendFiveHandler(webapp2.RequestHandler):
    def get(self):
        #find all users who want an email update every five minutes
        user_query = MyUser.query(MyUser.update_rate == 'every five minutes')
        users = user_query.fetch()

        #test
        # message = mail.EmailMessage()
        # message.sender = 'andrew.c.stier@gmail.com'
        # message.to = 'andrew.c.stier@gmail.com'
        # message.body = """Check the new trends!"""
        # message.send()

        for eachuser in users:
            message = mail.EmailMessage()
            message.subject = 'Your Connexus Update!'
            message.sender = 'andrew.c.stier@gmail.com'
            message.to = eachuser.email
            self.response.write(eachuser.email)
            message.body = """Check out what's trending! http://apt2015mp.appspot.com/trending"""
            message.send()

class SendHourHandler(webapp2.RequestHandler):
    def get(self):
        #find all users who want an email update every hour
        user_query = MyUser.query(MyUser.update_rate == 'every hour')
        users = user_query.fetch()

        #test
        # message = mail.EmailMessage()
        # message.sender = 'andrew.c.stier@gmail.com'
        # message.to = 'andrew.c.stier@gmail.com'
        # message.body = """Check the new trends!"""
        # message.send()

        for eachuser in users:
            message = mail.EmailMessage()
            message.subject = 'Your Connexus Update!'
            message.sender = 'andrew.c.stier@gmail.com'
            message.to = eachuser.email
            self.response.write(eachuser.email)
            message.body = """Check out what's trending! http://apt2015mp.appspot.com/trending"""
            message.send()

class SendDayHandler(webapp2.RequestHandler):
    def get(self):
        #find all users who want an email update every hour
        user_query = MyUser.query(MyUser.update_rate == 'every day')
        users = user_query.fetch()

        #test
        # message = mail.EmailMessage()
        # message.sender = 'andrew.c.stier@gmail.com'
        # message.to = 'andrew.c.stier@gmail.com'
        # message.body = """Check the new trends!"""
        # message.send()

        for eachuser in users:
            message = mail.EmailMessage()
            message.subject = 'Your Connexus Update!'
            message.sender = 'andrew.c.stier@gmail.com'
            message.to = eachuser.email
            self.response.write(eachuser.email)
            message.body = """Check out what's trending! http://apt2015mp.appspot.com/trending"""
            message.send()

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
    ('/sendfive', SendFiveHandler),
    ('/sendhour', SendHourHandler),
    ('/sendday', SendDayHandler),
    ], debug=True)