from datetime import datetime
from database import get_db
import uuid

class MKOVActions:
    @staticmethod
    def get_booking_confirmation(sid,bid=None):
        conn=get_db()
        if not bid:
            r=conn.execute("SELECT booking_id FROM bookings WHERE session_id=? ORDER BY created_at DESC LIMIT 1",(sid,)).fetchone()
            bid=r["booking_id"] if r else None
        if not bid: conn.close(); return{"status":"error","message":"No booking found."}
        b=conn.execute("SELECT * FROM bookings WHERE booking_id=?",(bid,)).fetchone(); conn.close()
        if not b: return{"status":"error","message":f"Booking '{bid}' not found."}
        return{"status":"success","action":"get_confirmation","message":f"✅ BOOKING CONFIRMED\n\nRef: {b['reference_code']}\nDest: {b['destination']}\nDates: {b['travel_dates']}\nPax: {b['group_size']}\nTotal: ₹{b['total_price']:,}\n\nItinerary shared within 24hrs."}

    @staticmethod
    def hold_booking(sid,dest=None,dates=None,hours=24):
        if not dest or not dates:
            conn=get_db(); l=conn.execute("SELECT l.destination,l.travel_dates FROM leads l JOIN sessions s ON s.lead_id=l.id WHERE s.session_id=?",(sid,)).fetchone(); conn.close()
            if l: dest=dest or l["destination"]; dates=dates or l["travel_dates"]
        if not dest: return{"status":"error","message":"Please share destination and dates first."}
        hid=f"HOLD-{str(uuid.uuid4())[:8].upper()}"
        conn=get_db(); conn.execute("INSERT INTO holds (session_id,hold_id,destination,travel_dates,hours) VALUES (?,?,?,?,?)",(sid,hid,dest,dates,hours)); conn.commit(); conn.close()
        return{"status":"success","action":"hold_booking","message":f"🔒 BOOKING HELD\n\nHold ID: {hid}\nDest: {dest}\nDates: {dates}\nValid: {hours}hrs — no payment needed.\n\nCall +91 8010700700 to finalise."}

    @staticmethod
    def cancel_booking(sid,bid=None,reason=None):
        if not bid:
            conn=get_db(); r=conn.execute("SELECT booking_id FROM bookings WHERE session_id=? ORDER BY created_at DESC LIMIT 1",(sid,)).fetchone(); conn.close()
            bid=r["booking_id"] if r else None
        if not bid: return{"status":"error","message":"No booking found."}
        conn=get_db(); b=conn.execute("SELECT * FROM bookings WHERE booking_id=?",(bid,)).fetchone()
        if not b: conn.close(); return{"status":"error","message":f"'{bid}' not found."}
        orig=b["total_price"] or 0; refund=int(orig*.75)
        conn.execute("UPDATE bookings SET status='cancelled',cancelled_at=? WHERE booking_id=?",(datetime.now().isoformat(),bid)); conn.commit(); conn.close()
        return{"status":"success","action":"cancel_booking","message":f"❌ CANCELLED\n\nRef: {b['reference_code']}\nOriginal: ₹{orig:,}\nRefund: 75% → ₹{refund:,}\n\nRefund in 5–7 business days."}

    _ANC={"travel_insurance":{"label":"Travel Insurance","price":2500},"visa_assistance":{"label":"Visa Assistance","price":1500},"hotel_upgrade":{"label":"Hotel Upgrade","price":5000},"airport_transfer":{"label":"Airport Transfer","price":1200},"activity_package":{"label":"Activity Package","price":3500},"meal_plan":{"label":"Meal Plan","price":2000},"travel_sim":{"label":"International SIM","price":800},"forex_card":{"label":"Forex Card","price":500}}

    @classmethod
    def add_ancillary(cls,sid,bid=None,atype=None,details=None):
        if not atype or atype not in cls._ANC: return{"status":"error","message":"Available: "+", ".join(cls._ANC.keys())}
        item=cls._ANC[atype]; aid=f"ANC-{str(uuid.uuid4())[:8].upper()}"
        conn=get_db(); conn.execute("INSERT INTO ancillaries (booking_id,ancillary_id,type,price,details) VALUES (?,?,?,?,?)",(bid or "PENDING",aid,atype,item["price"],str(details or {}))); conn.commit(); conn.close()
        return{"status":"success","action":"add_ancillary","message":f"✨ {item['label']} added — ₹{item['price']:,}\nID: {aid}"}

    @staticmethod
    def generate_payment_link(sid,bid=None):
        if not bid:
            conn=get_db(); r=conn.execute("SELECT booking_id FROM bookings WHERE session_id=? ORDER BY created_at DESC LIMIT 1",(sid,)).fetchone(); conn.close()
            bid=r["booking_id"] if r else None
        if not bid: return{"status":"error","message":"No booking found."}
        conn=get_db(); b=conn.execute("SELECT * FROM bookings WHERE booking_id=?",(bid,)).fetchone(); conn.close()
        if not b: return{"status":"error","message":f"'{bid}' not found."}
        link=f"https://pay.uniglobemkov.in/{bid}?token={str(uuid.uuid4())[:12]}"
        return{"status":"success","action":"payment_link","message":f"💳 PAYMENT LINK\n\nAmount: ₹{b['total_price']:,}\nLink: {link}\n\nAccepts UPI, Cards, Net Banking."}

    @staticmethod
    def process_custom_request(sid,text):
        tid=f"TKT-{str(uuid.uuid4())[:8].upper()}"
        conn=get_db(); conn.execute("INSERT INTO support_tickets (ticket_id,session_id,request_text) VALUES (?,?,?)",(tid,sid,text)); conn.commit(); conn.close()
        return{"status":"success","action":"custom_request","message":f"📋 TICKET: {tid}\n\nRequest: \"{text[:100]}\"\n\nSpecialist will call within 2 hours.\nOr call: +91 8010700700"}

actions=MKOVActions()
