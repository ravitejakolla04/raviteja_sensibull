from datetime import datetime, timedelta
from typing import final
from flask import Flask, sessions, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import urllib.request

app = Flask(__name__)

db = SQLAlchemy(app)

class Plans(db.Model):
    plan_id = db.Column(db.String(10), primary_key=True)
    validity = db.Column(db.Integer)
    cost = db.Column(db.Integer)

class Users(db.Model):
    user_name = db.Column(db.String(100), primary_key=True)
    created_at = db.Column(db.DateTime)

class UserPlans(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(100), db.ForeignKey(Users.user_name))
    plan_id = db.Column(db.String(10), db.ForeignKey(Plans.plan_id))
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)


@app.route("/")
def home():
    print("Home")

@app.route("/user/<name>", methods=["PUT", "GET"])
def user(name):
    print(request.method)
    if request.method == "PUT":
        current_user = Users.query.filter_by(user_name = name).first()
        if(current_user!=None):
            return jsonify({"status":200, "message":"User %s already exist" %name})
        current_time = datetime.now()
        db.session.add(Users(user_name=name, created_at = current_time))
        db.session.commit()
        return jsonify({"status":200, "message":"Success"})
    elif request.method == "GET":
        user_details = Users.query.filter_by(user_name = name).first()
        if(user_details == None):
            return jsonify({"status":400, "message":"User: %s does not exist" %name})
        if user_details:
            display_date = str(user_details.created_at)[:19]      #[:19] - slicing milliseconds
            return jsonify({"user_name":name, "created_at": display_date})
        


@app.route("/subscription", methods=["POST"])
def new_subscription():
    data = request.get_json()
    name = data.get("user_name")
    plan_id = data.get("plan_id")
    start = data.get("start_date")
    current_user = Users.query.filter_by(user_name = name).first()
    if(current_user == None):
        return jsonify({"status":400, "message":"User: %s does not exist" %name})
    start_date = datetime.strptime(start, '%Y-%m-%d').date()
    ends_on = start_date+timedelta(days=Plans.query.filter_by(plan_id=plan_id).first().validity)
    
    user_plans = UserPlans.query.filter_by(user_name=name).all()
    amount = 0
    plans_to_be_removed = []
    for plan in user_plans:
        if (plan.start_date.date()<start_date and plan.end_date.date()<start_date) or (plan.start_date.date()>ends_on and plan.end_date.date()>ends_on):
            continue
        if(start_date<=plan.start_date.date()):
            amount -= Plans.query.filter_by(plan_id=plan.plan_id).first().cost
        else:
            plan_details = Plans.query.filter_by(plan_id=plan_id).first()
            plan_cost_per_day = plan_details.cost/plan_details.validity
            amount -= (plan_details.cost - (((start_date-plan.start_date.date()).days)*plan_cost_per_day))
        plans_to_be_removed.append(plan)
    amount += Plans.query.filter_by(plan_id = plan_id).first().cost
    try:
        if(amount>0):
            payment_details = urllib.parse.urlencode({"user_name":"teja", "payment_type":"DEBIT", "amount":amount}).encode('utf-8')
        else:
            payment_details = urllib.parse.urlencode({"user_name":"teja", "payment_type":"CREDIT", "amount":(-1)*amount}).encode('utf-8')
        payment_request = urllib.request.Request("http://dummy-payment-server.herokuapp.com/payment", data=payment_details, headers={"content-type": "application/json", "Accept": "application/json",})
        payment_status = urllib.request.urlopen(payment_request) 
        response = payment_status.read().decode('utf8')
        if(response.status == "FAILED"):
            return "Unable to complete payment. Please try again"
    except Exception as e:
        print(e)

    for plan in plans_to_be_removed:
        db.session.delete(plan)
    db.session.add(UserPlans(user_name=name, plan_id=plan_id, start_date=start_date, end_date=ends_on))
    db.session.commit()

    user_plans = UserPlans.query.filter_by(user_name=name).all()
    for x in user_plans:
        print(x.plan_id, x.start_date, x.end_date)

    return jsonify({"status": "SUCCESS", "amount": str(-1*amount)}) 


@app.route("/subscription/<name>", methods=["GET"])
@app.route("/subscription/<name>/<date>", methods=["GET"])
def get_subscription(name, date=None):
    if(Users.query.filter_by(user_name = name).first()==None):
        return jsonify({"status":400, "message":"User: %s does not exist" %name})
    user_plans = UserPlans.query.filter_by(user_name=name).all()
    if date != None:
        date = datetime.strptime(date, '%Y-%m-%d').date()
        for plan in user_plans:
            end_date = plan.end_date.date()
            start_date = plan.start_date.date()
            if(start_date<=date and end_date>=date):
                return jsonify({"plan_id":plan.plan_id, "days_left":(end_date-date).days})
        return "You have not subscribed to any plan for the date: "+str(date)
    else:
        available_plans = []
        for plan in user_plans:
            available_plans.append({"plan_id": plan.plan_id, "start_date":str(plan.start_date.date()), "valid_till":str(plan.end_date.date())})
        if(len(available_plans)==0):
            return "You have not subscribed to any plan. Please subscribe"
        return str(available_plans)
        


if __name__ == "__main__":
    db.create_all()
    db.session.add(Plans(plan_id="FREE", validity= 0, cost= 0))
    db.session.add(Plans(plan_id="TRAIL", validity= 7, cost= 0))
    db.session.add(Plans(plan_id="LITE_1M", validity= 30, cost= 100))
    db.session.add(Plans(plan_id="PRO_1M", validity= 30, cost= 200))
    db.session.add(Plans(plan_id="LITE_6M", validity= 180, cost= 500))
    db.session.add(Plans(plan_id="PRO_6M", validity= 180, cost= 900))
    db.session.commit()
    app.run(port=19093)
