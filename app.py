
from flask import Flask, request, render_template, redirect, abort, url_for
from flask_cloudy import Storage
import libcloud.security
from flask_sqlalchemy import SQLAlchemy

libcloud.security.VERIFY_SSL_CERT = False


application = Flask(__name__)
application.config.from_object('config')
application.config.update({
    "STORAGE_PROVIDER": "",
    "STORAGE_CONTAINER": "",
    "STORAGE_KEY": "",
    "STORAGE_SECRET": "",
    "STORAGE_SERVER": True
})
db = SQLAlchemy(application)
storage = Storage()
storage.init_app(application)

#Model to save user information
class UserData(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(128), index=True, unique=False)
    files = db.relationship('FileData',secondary='user_file_map')
    def __init__(self, user):
        self.user = user

#Model to save file information
class FileData(db.Model):
    __tablename__ = 'file'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(128), index=True, unique=False)
    users = db.relationship('UserData',secondary='user_file_map')
   
    def __init__(self, filename):
        self.filename = filename

#Model to save file to user mapping
class UserFileMapData(db.Model):
    __tablename__ = 'user_file_map'
    userid = db.Column(db.Integer, db.ForeignKey('user.id'),primary_key=True)
    fileid = db.Column(db.Integer, db.ForeignKey('file.id'),primary_key=True)
    
    def __init__(self, userid,fileid):
        self.userid = userid
        self.fileid = fileid

#Returns a list of all users currently added to the server
def getUsers():
    users = UserData.query.order_by(UserData.user)
    userlist = []
    for user in users:
        userlist.append(user.user)
    return userlist

@application.route("/")
def index():
    return render_template("index.html", storage=storage,storageperuser=[],userlist=getUsers())

#Returns a view for the selected file
@application.route("/view/<path:object_name>")
def view(object_name):
    obj = storage.get(object_name)
    userlist = []
    file_data = FileData.query.filter_by(filename=object_name).first()
    users_for_file_data = UserFileMapData.query.filter_by(fileid=file_data.id).all()
    for user_for_file in users_for_file_data:
        u_data = UserData.query.filter_by(id=user_for_file.userid).first()
        userlist.append(u_data.user)
    return render_template("view.html", obj=obj,userlist=",".join(userlist))

#Get all files for a particular user
@application.route("/viewperuser", methods=["POST"])
def viewperuser():
    user = request.values['user']
    user_data = UserData.query.filter_by(user=user).first()
    result = []
    if not user_data:
        return render_template("index.html", storage=[])
    else:
        user_id = user_data.id
        files = UserFileMapData.query.filter_by(userid=user_id).all()
        for f in files:
            file_data = FileData.query.filter_by(id=f.fileid).first()
            if not file_data:
                continue
            else:
                fileobj = storage.get(file_data.filename)
                result.append(fileobj)
    return render_template("index.html",storage=storage,storageperuser=result,userlist=getUsers())

#Add users to the server
@application.route("/addUsers", methods=["POST"]) 
def addUsers():
    users = request.values['users'].split(',')
    for user in users:
        user_data = UserData.query.filter_by(user=user).first()
        if not user_data:
            data = UserData(user)
            db.session.add(data)
            db.session.commit()
    return render_template("index.html", storage=storage,storageperuser=[],userlist=getUsers())

#Add users to a particular file
@application.route("/addUsersToFile", methods=["POST"]) 
def addUsersToFile():
    users = request.values['users'].split(',')
    filename = request.values['filename']
    for user in users:
        user_data = UserData.query.filter_by(user=user).first()
        file_data = FileData.query.filter_by(filename=filename).first()
        if not user_data or not file_data:
            continue
        else:
            data = UserFileMapData(user_data.id,file_data.id)
            db.session.add(data)
            db.session.commit()
    return view(filename)

#Upload file to server
@application.route("/upload", methods=["POST"]) 
def upload():
    file = request.files.get("file")
    my_object = storage.upload(file,overwrite=True,public=True)
    filename =  my_object.name
    file_data = FileData.query.filter_by(filename=filename).first()
    if not file_data:
            data = FileData(filename)
            db.session.add(data)
            db.session.commit()
    return render_template("index.html", storage=storage,storageperuser=[],userlist=getUsers())

#Clean up everything from the server
@application.route("/deleteAll", methods=["POST"])
def deleteAll():
    db.session.query(UserFileMapData).delete()
    db.session.query(FileData).delete()
    db.session.query(UserData).delete()
    db.session.commit()
    for obj in storage:
        obj.delete()
    return render_template("index.html", storage=storage,storageperuser=[],userlist=getUsers())


if __name__ == "__main__":
    db.create_all()
    application.run(debug=True)