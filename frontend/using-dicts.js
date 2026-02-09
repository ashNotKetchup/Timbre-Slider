/**
 * Max for Live/Node.js script for communicating with a Python backend server via HTTP POST requests.
 * Handles asynchronous dictionary operations and message passing between Max and Python.
 *
 * Constants:
 * @constant {string} DICT_ID - The ID of the Max dict object used for storing representations.
 * @constant {string} PROTOCOL - The protocol used for HTTP requests (e.g., "http://").
 * @constant {string} HOST - The host address of the Python server.
 * @constant {number} PORT - The port number of the Python server.
 * @constant {string} URL - The full URL for sending requests to the Python server.
 *
 * Variables:
 * @type {Object} initialDict - The initial value for the dict, used for reset and test operations.
 *
 * Functions:
 * @function send
 * @description Sends a message to the Python server and returns the parsed JSON reply.
 * @param {Object} message - The message object to send (must include "type" and "content").
 * @returns {Promise<Object>} - The reply from the Python server.
 *
 * Max API Handlers:
 * @handler set
 * @description Updates a value at a given path in the dict and outputs the updated dict.
 * @param {string} path - The path in the dict to update.
 * @param {*} value - The value to set at the specified path.
 *
 * @handler test_set
 * @description Sets the dict to the initialDict value and outputs it.
 * @param {string} ID - The ID for the test set operation (not used).
 *
 * @handler reset
 * @description Resets the dict to its initial value and outputs it.
 *
 * @handler load
 * @description Sends a request to the Python server to encode an audio file to a latent representation.
 * Updates the dict with the returned latent representation.
 * @param {string} filepath - The file path of the audio file to encode.
 *
 * @handler load_folder
 * @description Sends a request to the Python server to load a folder and compute features for retraining.
 * @param {string} folderPath - The path to the folder containing audio files.
 *
 * @handler retrain_vae
 * @description Sends a request to the Python server to retrain the VAE using the most recently loaded features.
 *
 * @handler send
 * @description Sends the current dict as a latent representation to the Python server for decoding.
 * Outputs the dict after sending.
 *
 * @function main
 * @description Stores the initial value of the dict on process start for use in reset operations.
 *
 * Message Types (in line with udp_communication.py):
 * - "request_latent": Encodes audio to latent representation.
 * - "request_audio": Decodes latent representation to audio.
 * - "request_load_folder": Loads a folder and computes features for retraining.
 * - "request_retrain_vae": Retrains the VAE using loaded features.
 */
const maxApi = require("max-api");
const DICT_ID = "representations.dict";
// Destination settings
const PROTOCOL = "http://";
const HOST = "127.0.0.1";
const PORT = 5000;

const URL = `${PROTOCOL}${HOST}:${PORT}`;

// Used for storing the initial value
let initialDict = {
        "name": "Test Object",
        "tags": ["alpha", "beta", "gamma"],
        "scores": [10, 20, 30, 40],
        "position": { "x": 12.5, "y": -3.7 },
        "items": [
            {"id": 1, "label": "One"},
            {"id": 2, "label": "Two"}
        ]
    };


// 'representations.dict'

// Getting and setting dicts is an asynchronous process and the API function
// calls all return a Promise. We use the async/await syntax here in order
// to handle the async behaviour gracefully.
//
// Want to learn more about Promised and async/await:
//		* Web Fundamentals intro to Promises: https://developers.google.com/web/fundamentals/primers/promises
//		* Promises Deep Dive on MDN: https://developer.mozilla.org/en-US/docs/Learn/JavaScript/Asynchronous/Promises
//		* Web Fundamentals on using async/await and their benefits: https://developers.google.com/web/fundamentals/primers/async-functions
//		* Async Functions on MDN: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/async_function

// form for sending messages to python server and receiving replies
const send = async (message) => {	
	const res = await fetch(URL, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(message)
	});
	
	// python -> node response
	const reply = await res.json();
	console.log("Node received reply of type:", reply["type"]);
	return reply;
};

maxApi.addHandlers({
// Handle commands/messages from Max inlet
	set: async (path, value) => {
		const dict = await maxApi.updateDict(DICT_ID, path, value);
		await maxApi.outlet(dict);
	},
	test_set: async (ID) => {


		const dict = await maxApi.setDict(DICT_ID, initialDict);
		await maxApi.outlet(dict);
	},
	reset: async () => {
		const dict = await maxApi.setDict(DICT_ID, initialDict);
		await maxApi.outlet(dict);
	},
	// types of messages are 'load' ('request_latent' or 'encode') and 'send' (AKA 'sending_latent' or 'decode')
	load: async (filepath) => {
		// Node -> Python POST request

		message = {
		    "type": "request_latent", 
		    "content": filepath
		}
		
		reply = await send(message);
		// reply = {"type": "latent", "content": {"latent_vector": [0.1, 0.2, 0.3, 0.4]}};
		// data = reply["content"];

		if (reply["type"] == 'latent' ){
			console.log("Received latent representation from Python server: ", reply["content"]);
			dict = await maxApi.setDict(DICT_ID, reply["content"]);
			// for debugging:
			 await maxApi.outlet(dict);

			//  Necessary to signal Max that the dict has been updated
			await maxApi.outlet("Updated");
		}
	},
	load_folder: async (folderPath) => {
		const message = {
			"type": "request_load_folder",
			"content": folderPath
		};
		const reply = await send(message);
		if (reply["type"] === "load_folder_done") {
			console.log("Loaded folder and computed features:", reply["content"]);
			await maxApi.outlet("Folder loaded");
		} else {
			console.error("Failed to load folder:", reply);
			await maxApi.outlet("Folder load failed");
		}
	},
	retrain_vae: async () => {
		const message = {
			"type": "request_retrain_vae"
		};
		const reply = await send(message);
		if (reply["type"] === "retrain_done") {
			console.log("VAE retraining complete:", reply["content"]);
			await maxApi.outlet("Retrain done");
		} else {
			console.error("VAE retraining failed:", reply);
			await maxApi.outlet("Retrain failed");
		}
	},
	
	send: async () => {
		const dict = await maxApi.getDict(DICT_ID);
		let json;
		try {
			json = JSON.stringify(dict);
		} 
		catch (err) {
			console.error('Failed to stringify dict for sending:', err);
			json = '{}';
		}

		const prefix = 'request_audio';
		const message = {
			"type": prefix,
			"content": json
		}

		reply = await send(message);


		// Feedback via Max outlet
		const new_dict = JSON.parse(json)
		await maxApi.outlet(new_dict);
	},
}
);



// We use this to store the initial value of the dict on process start
// so that the call to "reset" and reset it accordingly
async function main() { 
	initialDict = await maxApi.getDict(DICT_ID); 
	// console.log("Storing initial dict value for reset:", initialDict);

}
main();


