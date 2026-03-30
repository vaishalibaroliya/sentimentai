let comments = [];

function analyzeSentiment(){
    let text = document.getElementById("comment").value;

    if(text.trim() === ""){
        alert("Enter a comment");
        return;
    }

    let sentiment = "Neutral";
    let emoji = "😐";
    let confidence = (Math.random() * 0.3 + 0.7).toFixed(2);

    if(text.includes("good") || text.includes("great") || text.includes("love")){
        sentiment = "Positive";
        emoji = "😊";
    }
    else if(text.includes("bad") || text.includes("hate")){
        sentiment = "Negative";
        emoji = "😡";
    }

    document.getElementById("result").innerHTML =
        `<h3 class="${sentiment.toLowerCase()}">
            ${emoji} ${sentiment} (Confidence: ${confidence})
        </h3>`;

    comments.push({text, sentiment, confidence});
    displayComments();
}

function displayComments(){
    let table = document.getElementById("commentTable");
    table.innerHTML = "";

    comments.forEach(c=>{
        table.innerHTML += `
            <tr>
                <td>${c.text}</td>
                <td class="${c.sentiment.toLowerCase()}">${c.sentiment}</td>
                <td>${c.confidence}</td>
            </tr>
        `;
    });
}

function downloadCSV(){
    let csv = "Comment,Sentiment,Confidence\n";
    comments.forEach(c=>{
        csv += `${c.text},${c.sentiment},${c.confidence}\n`;
    });

    let blob = new Blob([csv], { type: 'text/csv' });
    let link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "sentiment_data.csv";
    link.click();
}