

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
 * - "export_sound": Sends an export-sound event to the server for logging only (no-op).
 * - "save_logs" / "export_logs": Opens a save-file dialog on the server to export all logged requests/responses.
 */
const maxApi = require("max-api");
const DICT_ID = "representations.dict";
// Destination settings
const PROTOCOL = "http://";
const HOST = "127.0.0.1";
const PORT = 5000;

const URL = `${PROTOCOL}${HOST}:${PORT}`;

// List of regularisation options
let regularisationOptions = ['pca', 'raw_features', 'semantic'];
// Replace 'semantic' with 'audio_commons' if present
regularisationOptions = regularisationOptions.map(opt => opt === 'semantic' ? 'audio_commons' : opt);

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
const emitClientStatus = async (isAwaiting) => {
	try {
		await maxApi.outlet({ type: "client_busy", content: isAwaiting ? 1 : 0 });
	} catch (_) {
		// Non-fatal: status signaling should never break request flow.
	}
};

const sendToServer = async (message, timeoutMs = null) => {	
	const controller = new AbortController();
	const timer = timeoutMs !== null ? setTimeout(() => controller.abort(), timeoutMs) : null;
	await emitClientStatus(true);
	try {
		const res = await fetch(URL, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(message),
			signal: controller.signal
		});
		
		// python -> node response
		const reply = await res.json();
		console.log("Node received reply of type:", reply["type"]);
		return reply;
	} catch (err) {
		if (err.name === 'AbortError') {
			console.error("Request timed out after", timeoutMs, "ms");
			return { type: "error", content: "Request timed out" };
		}
		throw err;
	} finally {
		if (timer) clearTimeout(timer);
		await emitClientStatus(false);
	}
};

const isPlainObject = (value) => value !== null && typeof value === "object" && !Array.isArray(value);

const outletReplyDict = async (reply) => {
	if (isPlainObject(reply)) {
		await maxApi.outlet(reply);
	}
};

maxApi.addHandlers({
	set_regularisation: async (index) => {
		const idx = parseInt(index, 10);
		if (!isNaN(idx) && idx >= 0 && idx < regularisationOptions.length) {
			const selected = regularisationOptions[idx];
			console.log(`Regularisation set to: ${selected}`);
			// Send the choice to the Python server
			const message = {
				type: "set_regularisation",
				content: selected
			};
			try {
				const reply = await sendToServer(message);
				if (reply && reply.type === "set_regularisation_done") {
					await maxApi.outlet(`Regularisation set to: ${selected}`);
				} else {
					await maxApi.outlet("Failed to set regularisation");
				}
			} catch (err) {
				console.error("Error sending regularisation to server:", err);
				await maxApi.outlet("Error setting regularisation");
			}
		} else {
			console.warn('Invalid regularisation index:', index);
			await maxApi.outlet('Invalid regularisation index');
		}
	},
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
		//  Necessary to signal Max that the dict has been updated
		await maxApi.outlet("Updated");
	},
	// types of messages are 'load' ('request_latent' or 'encode') and 'send' (AKA 'sending_latent' or 'decode')
	load: async (filepath) => {
		// Node -> Python POST request

		const message = {
		    "type": "request_latent", 
		    "content": filepath
		};
		
		const reply = await sendToServer(message);

		if (reply["type"] == 'latent' ){
			console.log("Received latent representation from Python server: ", reply["content"]);
			await maxApi.setDict(DICT_ID, reply["content"]);
			// for debugging:
			 await maxApi.outlet(reply);

			//  Necessary to signal Max that the dict has been updated
			await maxApi.outlet("Updated");
		} else {
			await outletReplyDict(reply);
		}
	},
	load_folder: async (folderPath) => {
		const message = {
			"type": "request_load_folder",
			"content": folderPath
		};
		const reply = await sendToServer(message);
		await outletReplyDict(reply);
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
		const reply = await sendToServer(message);
		if (reply["type"] === "retrain_done") {
			console.log("VAE retraining complete:", reply["content"]);
			// If the reply includes latent data, update the dict
			if (reply["latent"]) {
				console.log("Received latent representation after retrain:", reply["latent"]);
				await maxApi.setDict(DICT_ID, reply["latent"]);
				await maxApi.outlet({ type: "latent", content: reply["latent"] });
				await maxApi.outlet("Updated");
			}
			await maxApi.outlet("Retrain complete");
		} else {
			await outletReplyDict(reply);
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

		const message = {
			"type": "request_audio",
			"content": json
		};

		const reply = await sendToServer(message);
		await outletReplyDict(reply);

		// Feedback via Max outlet
		const new_dict = JSON.parse(json);
		await maxApi.outlet(new_dict);
	},
	save_logs: async () => {
		console.log("Requesting server to save/export logs...");
		const message = { "type": "save_logs", "content": "" };
		try {
			const reply = await sendToServer(message);
			await outletReplyDict(reply);
			if (reply["type"] === "save_logs_done") {
				console.log("Logs saved:", reply["content"]);
				await maxApi.outlet("Logs saved");
			} else if (reply["type"] === "save_logs_cancelled") {
				console.log("Log save cancelled by user.");
				await maxApi.outlet("Log save cancelled");
			} else {
				console.error("Unexpected reply for save_logs:", reply);
				await maxApi.outlet("Log save failed");
			}
		} catch (err) {
			console.error("Error requesting log save:", err);
			await maxApi.outlet("Error saving logs");
		}
	},
		export_logs: async (...args) => {
			// Alias for save_logs
			return maxApi.handlers.save_logs(...args);
		},
		export_sound: async (...args) => {
			// Send an export_sound event to the server (logging only, no-op)
			const message = { "type": "export_sound", "content": args.length ? args[0] : "" };
			try {
				const reply = await sendToServer(message);
				await outletReplyDict(reply);
				console.log("export_sound logged:", reply);
				await maxApi.outlet("Export sound logged");
			} catch (err) {
				console.error("Error sending export_sound:", err);
				await maxApi.outlet("Error logging export sound");
			}
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


