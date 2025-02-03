async function getAvailableQuestions($fs) {
    var url = "/stats/available_questions";

    var $section = $fs.find('#id_question__section').eq(0);

    if ($section.val() == "") {
      return { results: [] };
    }

    var params = {
      s: $section.val(),
      ms: $fs.find('#session').eq(0).val()
    };


    url = url + '?' + $.param(params);

    const response = await fetch(url, {
        method: 'GET',
        mode: 'cors',
        credentials: 'same-origin',
        headers: {
            "Content-Type": 'application/x-www-form-urlencoded',
            "Accept": 'application/json; charset=utf-8',
        },
    })

    return response.json()
}

async function getAvailableOptions($fs) {
    var url = "/stats/available_options";

    var $question = $fs.find('#id_question').eq(0);

    if ($question.val() == "") {
      return { results: [] };
    }

    var params = {
      q: $question.val(),
      ms: $fs.find('#session').eq(0).val()
    };


    url = url + '?' + $.param(params);

    const response = await fetch(url, {
        method: 'GET',
        mode: 'cors',
        credentials: 'same-origin',
        headers: {
            "Content-Type": 'application/x-www-form-urlencoded',
            "Accept": 'application/json; charset=utf-8',
        },
    })

    return response.json()
}
$(function(){
  $('#id_question__section').on('change', function(e){
    var $d = $(this);
    var $fs = $d.parents('form');

    var $q = $fs.find('#id_question').eq(0);

    getAvailableQuestions($fs).then(function(data){
      if (data["results"].length > 0) {
        $q.empty()
        let $blank = $('<option></option>').attr('value', "").text("---------");
        $q.append($blank);
        $.each(data["results"], function(i, opt) {
          let $o = $('<option></option>').attr('value', opt["id"]).text(opt["number_and_part"]);
          $q.append($o)
        });
      }
    });
  });

  $('#id_question').on('change', function(e){
    var $d = $(this);
    var $fs = $d.parents('form');

    var $opt = $fs.find('#id_option').eq(0);

    getAvailableOptions($fs).then(function(data){
      if (data["results"].length > 0) {
        $opt.empty()
        let $blank = $('<option></option>').attr('value', "").text("---------");
        $opt.append($blank);
        $.each(data["results"], function(i, opt) {
          let $o = $('<option></option>').attr('value', opt["id"]).text(opt["description"]);
          $opt.append($o)
        });
      }
    });
  });
});
