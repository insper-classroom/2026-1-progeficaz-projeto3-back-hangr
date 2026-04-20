const path = require("path");
require("dotenv").config({
  path: path.join(__dirname, ".env"),
  quiet: true
});

const query = process.argv[2];
const cidade = process.argv[3];

async function run() {
  try {
    const key = process.env.FOURSQUARE_API_KEY;

    if (!key) {
      console.error("FOURSQUARE_API_KEY not found in .env");
      process.exit(1);
    }

    const url = `https://places-api.foursquare.com/places/search?query=${encodeURIComponent(query)}&near=${encodeURIComponent(cidade)}&limit=5`;

    const res = await fetch(url, {
      headers: {
        "Accept": "application/json",
        "Authorization": `Bearer ${key}`,
        "X-Places-Api-Version": "2025-06-17",
      },
    });

    const text = await res.text();

    if (!res.ok) {
      console.error("STATUS:", res.status);
      console.error("BODY:", text);
      process.exit(1);
    }

    // Only JSON to stdout
    process.stdout.write(text);

  } catch (err) {
    console.error("ERROR:", err);
    process.exit(1);
  }
}

run();