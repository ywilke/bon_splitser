function incCount(priceId) {
    document.getElementById(priceId).value++;
}

function decCount(priceId) {
    var count = document.getElementById(priceId).value;
    if (count < 1) {
        return;
    } else {
        document.getElementById(priceId).value--;
    }
}

// users input list
var counter = 3;

function addInput(){
    var newuser = document.createElement("input");
    newuser.type = "text";
    newuser.classList.add("form-control", "my-3");
    newuser.size = "16";
    newuser.style.width = "auto";
    newuser.placeholder = "Deelnemer " + counter;
    newuser.name = "users[]";
    document.getElementById('user_forms').appendChild(newuser);
    counter++;
}

