import webapp2
import os
import urllib
import jinja2
import datetime
import cgi
import re

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

admin_email = "vechema@gmail.com"
app_url = "http://apt2015mini.appspot.com/trending"


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
    update_date = ndb.DateProperty()
    subscribers = ndb.StringProperty(repeated=True)
    tags = ndb.StringProperty(repeated=True)
    cover_url = ndb.StringProperty()
    photos = ndb.StructuredProperty(Picture, repeated=True)
    num_pics = ndb.ComputedProperty(lambda e: len(e.photos))
    view_count = ndb.DateTimeProperty(repeated=True)
    count = ndb.ComputedProperty(lambda e: len(e.view_count))


class Leaders(ndb.Model):
    champs = ndb.KeyProperty(repeated=True)


class MyUser(ndb.Model):
    streams_own = ndb.KeyProperty(repeated=True)  # Going to hold stream keys
    streams_subscribe = ndb.KeyProperty(repeated=True)  # Going to hold stream keys
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
        elif error_code == "nosuchstream":
            message = "You tried to view a stream that doesn't exist"
        elif error_code == "social":
            message = "Yeah, we didn't implement social"
        elif error_code == "nofile":
            message = "You tried to add an image without selecting a file"
        elif error_code == "nosubscribe":
            message = 'You cannot subscribe unless you are <a href="/login">logged</a> in'
        elif error_code == "streamnamecontents":
            message = 'Stream names must be alphanumeric, space, or underscores'
        else:
            message = 'Error'

        template_values = {
            'message': message,
        }
        template = JINJA_ENVIRONMENT.get_template('templates/error.html')
        self.response.write(template.render(template_values))


class ViewAllHandler(webapp2.RequestHandler):
    def get(self):
        stream_query = Stream.query().order(-Stream.creation_date)
        streams = stream_query.fetch(400)

        template_values = {
            'streams': streams
        }
        template = JINJA_ENVIRONMENT.get_template('templates/viewall.html')
        self.response.write(template.render(template_values))


def create_dummy():
    non_user = MyUser(id='dummy', email='dummy', update_rate='never')
    non_user.put()


def format_email(email):
    email = email.lower()
    index = email.index('@')
    email_front = email[:index]
    email_front_format = email_front.replace('.','')
    return email_front_format + email[index:]


class ViewAHandler(webapp2.RequestHandler):
    def get(self):
        stream_name = self.request.get('stream')
        viewall = self.request.get('viewall')

        stream_query = Stream.query(Stream.name == stream_name)
        streams = stream_query.fetch()
        if len(streams) == 0:
            self.redirect('/error?message=nosuchstream')
            return
        stream = streams[0]

        # add the current date and time to the stream's view_count list if viewer is not stream owner
        views = stream.view_count
        now = datetime.datetime.now()

        # Check that the user is not the one viewing the stream
        # If the user is not signed in, it counts as a view
        user = users.get_current_user()
        if not user:
            views.append(now)
            user_key = ndb.Key(MyUser, 'dummy')
            if user_key.get() == None:
                create_dummy()
        # If the user is signed it, check that this is not one of their streams
        else:
            user_email = format_email(user.email())
            user_key = ndb.Key(MyUser, user_email)

            # confirm or create MyUser object
            if (user_key.get() == None):
                NewUser = MyUser(id = user_email, email = user_email,update_rate = 'never')
                NewUser.put()

            currentuser = user_key.get()

            # Is user's stream keys do not contain this stream key, add view to stream's view queue
            if stream.key not in currentuser.streams_own:
                views.append(now)

        # Purge hour old views
        hourback = now - datetime.timedelta(hours = 1)
        # self.response.write(hourback)

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
        if not viewall:
            if limit > hard_limit:
                limit = hard_limit

        for i in range(0,limit):
            photo_url_list.append(get_serving_url(pics[i].blob_key))

        if not user:
            my_user = ndb.Key(MyUser, 'dummy').get()
        else:
            user_email = format_email(user.email())
            my_user = ndb.Key(MyUser, user_email).get()

        view_all = self.request.get('viewall')

        template_values = {
            'stream' : stream,
            'upload_url' : upload_url,
            'photo_url_list' : photo_url_list,
            'user' : my_user,
            'stream_name' : stream.name,
            'num_pics' : len(pics),
            'view_all' : view_all,
        }
        template = JINJA_ENVIRONMENT.get_template('templates/viewa.html')
        self.response.write(template.render(template_values))
        # self.response.write(stream.count)
        # for view in views:
        #     self.response.write(str(view) + '<br>')

class MorePicsHandler(webapp2.RequestHandler):
    def get(self):
        stream_name = self.request.get('stream')
        stream_query = Stream.query(Stream.name == stream_name)
        streams = stream_query.fetch()
        stream = streams[0]
        photo_url_list = []
        pics = stream.photos

        if(len(pics) > 3):
            for i in range(3,len(pics)):
                photo_url_list.append(get_serving_url(pics[i].blob_key))

        template_values = {
            'photo_url_list' : photo_url_list,
            'stream_name' : stream_name
        }
        template = JINJA_ENVIRONMENT.get_template('templates/morepics.html')
        self.response.write(template.render(template_values))

class SubscribeHandler(webapp2.RequestHandler):
    def post(self):
        stream_name = self.request.get('stream')
        stream_query = Stream.query(Stream.name == stream_name)
        streams = stream_query.fetch()
        stream = streams[0]
        # stream = ndb.Key(Stream, stream_name)

        user = users.get_current_user()
        user_email = format_email(user.email())
        userkey = ndb.Key(MyUser, user_email)

        # confirm or create MyUser object
        if (userkey.get() == None):
            NewUser = MyUser(id = user_email, email = user_email,update_rate = 'never')
            NewUser.put()

        currentuser = userkey.get()
        currentuser.streams_subscribe.append(stream.key)

        currentuser.put()

        self.redirect('/view?stream=' + stream_name)


class UnsubscribeHandler(webapp2.RequestHandler):
    def post(self):
        stream_names = self.request.get_all('stream_name')

        user = users.get_current_user()
        user_email = format_email(user.email())
        cur_user = ndb.Key(MyUser, user_email).get()

        subs_to_remove = []
        for sub in cur_user.streams_subscribe:
            stream = sub.get()
            for name in stream_names:
                if stream.name == name:
                    subs_to_remove.append(sub)

        new_sub_list = []
        for sub in cur_user.streams_subscribe:
            if sub not in subs_to_remove:
                new_sub_list.append(sub)

        cur_user.streams_subscribe = new_sub_list

        cur_user.put()

        self.redirect('/manage')


class DeleteHandler(webapp2.RequestHandler):
    def post(self):

        stream_names = self.request.get_all('stream_name')

        # Delete it in MyUser.streams_own
        user = users.get_current_user()
        user_email = format_email(user.email())
        cur_user = ndb.Key(MyUser, user_email).get()

        owns_to_remove = []
        for owned in cur_user.streams_own:
            stream = owned.get()
            for name in stream_names:
                if stream.name == name:
                    owns_to_remove.append(owned)

        new_own_list = []
        for owned in cur_user.streams_own:
            if owned not in owns_to_remove:
                new_own_list.append(owned)

        cur_user.streams_own = new_own_list
        cur_user.put()

        # Delete it in MyUser.streams_subscribe
        user_query = MyUser.query()
        myusers = user_query.fetch(400)
        if len(myusers) > 0:
            for myuser in myusers:
                subs_to_remove = []
                for sub in myuser.streams_subscribe:
                    stream = sub.get()
                    for name in stream_names:
                        if stream.name == name:
                            subs_to_remove.append(sub)

                new_sub_list = []
                for sub in myuser.streams_subscribe:
                    if sub not in subs_to_remove:
                        new_sub_list.append(sub)

                myuser.streams_subscribe = new_sub_list
                myuser.put()

        # Need to delete the stream & its pictures
        for stream_name in stream_names:
            stream_query = Stream.query(Stream.name == stream_name)
            streams = stream_query.fetch()
            stream = streams[0]

            # Trying to delete the picture but only delete it being held in a stream
            # for pic in stream.photos:
            #    pic.key.delete()

            # stream deleted
            stream.key.delete()

        self.redirect('/manage')
        # self.redirect('/view?stream=')


class PhotoUploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        if len(self.get_uploads()) == 0:
            self.redirect('/error?message=nofile')
            return
        # Get the blob_key
        upload = self.get_uploads()[0]

        # Get stream, name & comments
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

        # Add the picture to it's stream
        stream_query = Stream.query(Stream.name == stream_name)
        streams = stream_query.fetch()
        stream = streams[0]

        list_pics = stream.photos
        list_pics.insert(0, user_photo)
        # list_pics.append(user_photo)
        stream.photos = list_pics
        # stream.photos.append(user_photo)
        # stream.photos[0] = user_photo
        stream.update_date = datetime.datetime.now()
        stream.put()

        self.redirect('/view?stream=' + stream_name)
        # self.redirect('/')


class AllPhotosHandler(webapp2.RequestHandler):
    def get(self):

        photo_query = Picture.query().order(-Picture.upload_date)
        photos = photo_query.fetch()

        template_values = {
            'photos': photos,
        }
        template = JINJA_ENVIRONMENT.get_template('templates/allpics.html')
        self.response.write(template.render(template_values))


class CreateHandler(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return

        template_values = {
        }
        template = JINJA_ENVIRONMENT.get_template('templates/create.html')
        self.response.write(template.render(template_values))

    def post(self):
        # Get the name of the stream
        stream_name = self.request.get('streamname')
        if re.match('^[\w\s]+$', stream_name) is None:
            self.redirect('/error?message=streamnamecontents')
            return
        if len(stream_name) == 0:
            self.redirect('/error?message=streamnamelen')
            return
        # Need to see if a stream with that name already exists
        stream_query = Stream.query(Stream.name == stream_name)
        streams = stream_query.fetch(400)
        if streams:
            self.redirect('/error?message=streamnamedup')
            return

        # get the emails and then send 'em
        # emails = re.split(",| ",self.request.get('subscribers'))
        emails = self.request.get('subscribers').replace(" ","").split(",")
        email_message = self.request.get('message')
        # Need to change this to the actual url of the stream
        stream_url = "http://apt2015mini.appspot.com/view?stream=" + urllib.quote_plus(stream_name)
        sendSubscriptionEmails(emails, email_message, stream_url)

        # tags
        tag_list = self.request.get('tags').replace('#', '').split(" ")

        #cover image
        cover = self.request.get('coverurl')
        if len(cover) == 0:
            cover = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/No_image_available.svg/300px-No_image_available.svg.png"

        #Put it all together in a stream object
        safe_name_url = urllib.quote_plus(stream_name)
        stream = Stream()
        stream.name = stream_name
        stream.id = stream_name
        stream.name_safe = safe_name_url
        stream.subscribers = emails
        stream.tags = tag_list
        stream.cover_url = cover

        stream.put()

        #Now I need to sign people up by their emails
        if emails[0] != "":
            for sub_email in emails:
                sub_email_use = sub_email.replace(' ', '')
                user_email = format_email(sub_email_use)
                subscriber_key = ndb.Key(MyUser, user_email)
                if subscriber_key.get() is None:
                    new_user = MyUser(id = user_email, email = user_email,update_rate = 'never')
                    new_user.put()

                user_sub = subscriber_key.get()
                user_sub_email = format_email(user_sub.email)
                user_email = format_email(users.get_current_user().email())
                if user_email != user_sub_email:
                    user_sub.streams_subscribe.append(stream.key)
                user_sub.put()
                self.response.write('<br>' +user_sub.email)
                self.response.write('<br>' +sub_email)

        #Need to set the user as the owner
        user = users.get_current_user()
        user_email = format_email(user.email())
        userkey = ndb.Key(MyUser, user_email)

        if (userkey.get() == None):
            NewUser = MyUser(id = user_email, email = user_email,update_rate = 'never')
            NewUser.put()

        user_owner = userkey.get()
        user_owner.streams_own.append(stream.key)
        user_owner.put()
        self.response.write('<br>' +user_owner.email)
        self.response.write('<br>' +user.email())

        #self.redirect('/' + garb)
        #self.redirect('/manage')
        #self.redirect('/' + user_owner.email)


def sendSubscriptionEmails(emails, note, stream_url):
    user = users.get_current_user()
    for email in emails:
        if len(email) > 0:
            message = mail.EmailMessage(sender=user.email(),
                                    subject="APT_Fall_15: Mini-project Subscription")

            message.to = email
            message.body = note + """

            This message was sent by """ + stream_url + """

            -Jo Egner and Andrew Stier
            """

            message.send()


class ManageHandler(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        user_email = format_email(user.email())
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return

        #confirm or create MyUser object
        #MyUser instances are stored in blobstore using the user email as a key (id)
        userkey = ndb.Key(MyUser, user_email)

        if userkey.get() is None:
            NewUser = MyUser(id = user_email, email = user_email,update_rate = 'never')
            NewUser.put()

        # ThisUser = userkey.get()
        # self.response.write(ThisUser.email)
        # self.response.write(ThisUser.update_rate)
        current_user = userkey.get()
        name = user.nickname()
        template_values ={
            'name' : name,
            'current_user' : current_user,
        }
        template = JINJA_ENVIRONMENT.get_template('templates/manage.html')
        self.response.write(template.render(template_values))


class MainPage(webapp2.RequestHandler):
    def get(self):
        self.redirect('/viewall')


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
            pic_query = Picture.query()
            pics = pic_query.fetch(400)
            index = 0
            if len(pics) > 0:
                for result in pics:
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

        try:
            user_query = MyUser.query()
            users = user_query.fetch(400)
            index = 0
            if len(users) > 0:
                for result in users:
                    result.key.delete()
                    index+=1

            hour = datetime.datetime.now().time().hour
            minute = datetime.datetime.now().time().minute
            second = datetime.datetime.now().time().second
            user_message = (str(index) + ' items deleted from MyUser at ' + str(hour) + ':' + str(minute) + ':' + str(second)+'\n\n')
            if index == 400:
                self.redirect("/purge")


        except Exception, e:
 #           self.response.out.write('Error is: ' + repr(e) + '\n')
            pass

        try:
            leader_query = Leaders.query()
            leaders = leader_query.fetch(400)
            index = 0
            if len(leaders) > 0:
                for result in leaders:
                    result.key.delete()
                    index+=1

            hour = datetime.datetime.now().time().hour
            minute = datetime.datetime.now().time().minute
            second = datetime.datetime.now().time().second
            leader_message = (str(index) + ' items deleted from Leaders at ' + str(hour) + ':' + str(minute) + ':' + str(second)+'\n\n')
            if index == 400:
                self.redirect("/purge")


        except Exception, e:
 #           self.response.out.write('Error is: ' + repr(e) + '\n')
            pass

        template_values ={
            'blob_message' : blob_message,
            'stream_message' : stream_message,
            'pic_message' : pic_message,
            'user_message' : user_message,
            'leader_message' : leader_message,
        }
        template = JINJA_ENVIRONMENT.get_template('templates/purge.html')
        self.response.write(template.render(template_values))


class TrendingHandler(webapp2.RequestHandler):
    def get(self):
        #Find current update rate
        #Check to make sure there is a user object
        user = users.get_current_user()
        user_email = format_email(user.email())
        if user:

            #confirm or create MyUser object
            userkey = ndb.Key(MyUser, user_email)

            if (userkey.get() == None):
                NewUser = MyUser(id = user_email, email = user_email,update_rate = 'never')
                NewUser.put()

            currentrate = userkey.get().update_rate

        else:
            currentrate = 'N/A'


        #set already known key for leader information
        thekey = ndb.Key(Leaders, 'lkey')

        #check to see if leader information is available yet
        if(thekey.get()==None):
            leaders = []

        else:
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
        user_email = format_email(user.email())
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return

        #confirm or create MyUser object
        #MyUser instances are stored in blobstore using the user email as a key (id)
        userkey = ndb.Key(MyUser, user_email)

        if (userkey.get() == None):
            NewUser = MyUser(id = user_email, email = user_email,update_rate = 'never')
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
            message.sender = admin_email
            message.to = eachuser.email
            self.response.write(eachuser.email)
            message.body = """Check out what's trending! """ + app_url
            message.send()


class SendHourHandler(webapp2.RequestHandler):
    def get(self):
        #find all users who want an email update every hour
        user_query = MyUser.query(MyUser.update_rate == 'every hour')
        users = user_query.fetch()

        ##test
        # message = mail.EmailMessage()
        # message.sender = 'andrew.c.stier@gmail.com'
        # message.to = 'andrew.c.stier@gmail.com'
        # message.body = """Check the new trends!"""
        # message.send()

        for eachuser in users:
            message = mail.EmailMessage()
            message.subject = 'Your Connexus Update!'
            message.sender = admin_email
            message.to = eachuser.email
            self.response.write(eachuser.email)
            message.body = """Check out what's trending! """ + app_url
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
            message.sender = admin_email
            message.to = eachuser.email
            self.response.write(eachuser.email)
            message.body = """Check out what's trending! """ + app_url
            message.send()

class SearchHandler(webapp2.RequestHandler):
    def get(self):

        template_values ={}
        template = JINJA_ENVIRONMENT.get_template('templates/search.html')
        self.response.write(template.render(template_values))


        query_list = self.request.get('thequery').replace(',', '').split(" ")
        allstreams = []
        for eachquery in query_list:
            stream_query = Stream.query(ndb.OR(Stream.name == eachquery,
                                            Stream.tags == eachquery))
            streams = stream_query.fetch()
            allstreams = allstreams + streams

        for stream in allstreams:
            self.response.write(stream.name)
            self.response.write('<br>')

class SearchHandler(webapp2.RequestHandler):
    def get(self):

        template_values ={}
        template = JINJA_ENVIRONMENT.get_template('templates/search.html')
        self.response.write(template.render(template_values))


        # query_list = self.request.get('thequery').replace(',', '').split(" ")
        # allstreams = []
        # for eachquery in query_list:
        #     stream_query = Stream.query(ndb.OR(Stream.name == eachquery,
        #                                     Stream.tags == eachquery))
        #     streams = stream_query.fetch()
        #     allstreams = allstreams + streams
        #
        # for stream in allstreams:
        #     self.response.write(stream.name)
        #     self.response.write('<br>')

class SearchResultsHandler(webapp2.RequestHandler):
    def get(self):

        template_values = {}
        template = JINJA_ENVIRONMENT.get_template('templates/search.html')
        self.response.write(template.render(template_values))


        query_list = self.request.get('thequery').replace(',', '').split(" ")
        #allstreams = []
        stream_query = Stream.query()
        for eachquery in query_list:
            stream_query = stream_query.filter(ndb.OR(eachquery == Stream.name,
                                                Stream.tags == eachquery))
            #allstreams = allstreams + streams

        allstreams = stream_query.order(-Stream.creation_date).fetch(5)
        result_count = len(allstreams)
        template_values ={
            'streams' : allstreams,
            'count' : result_count,
            'query' : self.request.get('thequery'),
        }
        template = JINJA_ENVIRONMENT.get_template('templates/results.html')
        self.response.write(template.render(template_values))





app = webapp2.WSGIApplication([
    ('/allpics', AllPhotosHandler),
    ('/error', ErrorHandler),
    ('/viewall', ViewAllHandler),
    ('/upload_photo', PhotoUploadHandler),
    ('/view', ViewAHandler),
    ('/morepics', MorePicsHandler),
    ('/subscribe', SubscribeHandler),
    ('/unsubscribe', UnsubscribeHandler),
    ('/delete', DeleteHandler),
    ('/create', CreateHandler),
    ('/manage', ManageHandler),
    ('/login', LoginHandler),
    ('/', MainPage),
    ('/purge', PurgeHandler),
    ('/trending', TrendingHandler),
    ('/search', SearchHandler),
    ('/searchresults', SearchResultsHandler),
    ('/update', UpdateHandler),
    ('/sendfive', SendFiveHandler),
    ('/sendhour', SendHourHandler),
    ('/sendday', SendDayHandler),
    ], debug=True)