require('dotenv').config();
const axios = require('axios');
const fs = require('fs');
const path = require('path');

async function fetchData() {
  const endpoint = process.env.DATA_ENDPOINT;
  const token = process.env.API_TOKEN;

  if (!endpoint ||!token || token === 'your_api_key_here') {
    console.error('Error: DATA_ENDPOINT or API_TOKEN is not properly defined in.env file.');
    process.exit(1);
  }

  console.log(`Fetching data from: ${endpoint}...`);

  try {
    const response = await axios.get(endpoint, {
      headers: {
        'X-API-credential': token 
      }
    });

    // Socrata/NYC Open Data API often returns data in a specific format.
    // For query.json endpoints, the data is usually directly in the response or in a 'data' field.
    const data = response.data.data || response.data;

    const outputPath = path.join(__dirname, '..', 'data', 'estaurants.json');
    
    // Ensure data directory exists
    const dir = path.join(__dirname, '..', 'data');
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    fs.writeFileSync(outputPath, JSON.stringify(data, null, 2));
    console.log(`Successfully saved ${Array.isArray(data)? data.length : 0} records to ${outputPath}`);

  } catch (error) {
    console.error('Error fetching data:', error.message);
    if (error.response) {
      console.error('Status:', error.response.status);
      console.error('Data:', error.response.data);
    }
  }
}

fetchData();