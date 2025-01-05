from flask import Flask, jsonify, request
import sqlite3

app = Flask(__name__)

@app.route('/messages')
def messages():
    last_message_id = request.args.get('last_message_id', type=int, default=-1)
    print(last_message_id)
    
    connection = sqlite3.connect("trenchy.db")
    try:
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        try:
            cursor.execute("""
                SELECT id, message, timestamp 
                FROM messages 
                WHERE id > ? 
                ORDER BY id DESC
                LIMIT 100
            """, (last_message_id,))
            
            return jsonify([dict(row) for row in cursor.fetchall()])
        finally:
            cursor.close()
    finally:
        connection.close()

if __name__ == '__main__':
    app.run(port=28273)