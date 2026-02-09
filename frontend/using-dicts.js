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


