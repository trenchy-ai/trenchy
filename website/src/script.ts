import { WebRTCPlayer } from '@eyevinn/webrtc-player';

const messagesElement = document.getElementById('messages');
let lastMessageId = -1;

async function main() {
  console.log('Loading player');
  const player = new WebRTCPlayer({
    video: document.querySelector('video'),
    type: 'whep',
    mediaConstraints: {
      videoOnly: true,
    },
  });

  await player.load(new URL(atob(
    'aHR0cHM6Ly9jdXN0b21lci1xMHU5eG8yM2VxdTIxdGYzLmNsb3VkZmxhcmVzdHJlYW0uY29tLzRiMTRhM2Y0NjI2ZTBmNzdkNTgxNjVjYTVjOTlmMTcyL3dlYlJUQy9wbGF5'
  )));

  updateMessages();  
  setInterval(updateMessages, 10000);
}

async function updateMessages() {
  console.log('Updating messages');
  const response = await fetch(`https://api.trenchy.ai/messages?last_message_id=${lastMessageId}`);
  const messages = await response.json();
  if (messages.length > 0) {
    lastMessageId = messages[0].id;
    for (let i = messages.length - 1; i >= 0; i--) {
      messagesElement.prepend(renderMessage(messages[i]));
    }
  }

  // Update timestamps
  const timestamps = Array.from(document.getElementsByClassName('timestamp'));
  for (const timestamp of timestamps) {
    timestamp.textContent = getTime(timestamp.getAttribute('data-timestamp'));
  }
};

function renderMessage(message: {category: string, id: number, message: string, timestamp:string}){
  const emoji =
    message.category === 'researching' ? '🔬' :
    message.category === 'buying' ? '💰' :
    message.category === 'not_buying' ? '🚫' :
    message.category === 'considering_selling' ? '🤔' :
    message.category === 'selling' ? '💸' :
    message.category === 'not_selling' ? '⏳' : '';

  const categorySpan = document.createElement('span');
  categorySpan.textContent = `${emoji} ${message.category} - `;

  const timeSpan = document.createElement('span');
  timeSpan.className = 'timestamp';
  timeSpan.setAttribute('data-timestamp', message.timestamp);
  timeSpan.textContent = `${getTime(message.timestamp)}`;

  const contentDiv = document.createElement('div');
  contentDiv.className = 'message-content';
  contentDiv.innerHTML = message.message.replace(/\n/g, '<br>');

  const messageDiv = document.createElement('div');
  messageDiv.className = 'message';
  messageDiv.appendChild(categorySpan);
  messageDiv.appendChild(timeSpan);
  messageDiv.appendChild(contentDiv);
  return messageDiv;
}

// Returns a time like "5 sec ago"
function getTime(timestamp: string): string {
  const seconds = Math.floor(((Date.now()/1000) - parseInt(timestamp)));
  return (
    seconds < 60 ? `${seconds} sec ago` :
    seconds < 3600 ? `${Math.floor(seconds / 60)} min ago` :
    seconds < 86400 ? `${Math.floor(seconds / 3600)} min ago` :
    `${Math.floor(seconds / 86400)} days ago`
  );
}

main().catch(e => { console.error(e) });
