//alert('Hello World!');
//var msg = 'Some random message';
//console.log(x);

$(document).ready(function(){
    $("div").mouseenter(function(){
       $("div").fadeTo('fast',1) 
    
    });
    $("div").mouseleave(function(){
       $("div").fadeTo('fast',0.5) 
    
    });
});