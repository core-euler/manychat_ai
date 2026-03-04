# Chat Completions

## OpenAPI Specification

```yaml
openapi: 3.0.1
info:
  title: ''
  description: ''
  version: 1.0.0
paths:
  /v1/chat/completions:
    post:
      summary: Chat Completions
      deprecated: false
      description: >-
        ## Overview


        `chat/completions` is the most common API endpoint for LLMs, which takes
        **a conversation list composed of multiple messages** as input to get
        model responses.


        ### Important Notes


        ⚠️ **Model Differences**  

        Different model providers may support different request parameters and
        return different response fields. We strongly recommend consulting the
        official documentation of the respective model provider for complete
        parameter lists and usage instructions.


        ⚠️ **Response Pass-through Principle**  

        **CometAPI typically does not modify model responses outside of reverse
        format**, ensuring you receive response content consistent with the
        original API.


        ⚠️ **OpenAI Pro Model Limitation**  

        For OpenAI Pro series models, please use the
        [`responses`](https://apidoc.cometapi.com/responses) endpoint.


        ### Reference Documentation


        For more details about the `chat/completions` endpoint, we recommend
        referring to the [OpenAI Official
        Documentation](https://platform.openai.com/docs/api-reference/chat).


        **OpenAI Related Guides:**


        - [Quick
        Start](https://platform.openai.com/docs/quickstart?api-mode=chat)

        - [Text
        Input/Output](https://platform.openai.com/docs/guides/text?api-mode=chat)

        - [Image
        Input](https://platform.openai.com/docs/guides/images?api-mode=chat)

        - [Audio
        Input/Output](https://platform.openai.com/docs/guides/audio?api-mode=chat)

        - [Structured
        Output](https://platform.openai.com/docs/guides/structured-outputs?api-mode=chat)

        - [Function
        Calling](https://platform.openai.com/docs/guides/function-calling?api-mode=chat)

        - [Conversation State
        Management](https://platform.openai.com/docs/guides/conversation-state?api-mode=chat)


        ---



        ## API Reference


        ### Request Parameters


        #### Required Parameters


        **`model`** _string_ **required**  

        Specifies the model ID to use for generating responses.


        ```json

        {
          "model": "gpt-4"
        }

        ```


        **`messages`** _array_ **required**  

        List of conversation messages containing roles and content. Each message
        should include:


        - **`role`** _string_ - The role of the message, options:
          - `system` - System message for setting assistant behavior
          - `user` - User message
          - `assistant` - Assistant's historical replies

        - **`content`** _string_ - The specific content of the message


        ```json

        {
          "messages": [
            {
              "role": "system",
              "content": "You are a professional AI assistant"
            },
            {
              "role": "user",
              "content": "What is machine learning?"
            }
          ]
        }

        ```


        #### Optional Parameters


        **`stream`** _boolean_ **optional**  

        Whether to enable streaming response. When set to `true`, the response
        will be returned in chunks as Server-Sent Events (SSE).


        - Default: `false`


        ```json

        {
          "stream": true
        }

        ```


        **`temperature`** _number_ **optional**  

        Controls the randomness of responses, range 0-2.


        - Lower values (e.g., 0.2): More deterministic and focused

        - Higher values (e.g., 1.8): More random and creative


        **`max_tokens`** _integer_ **optional**  

        Limits the maximum number of tokens to generate.


        **`top_p`** _number_ **optional**  

        Nucleus sampling parameter, range 0-1. It's not recommended to adjust
        both `temperature` and `top_p` simultaneously.


        ---



        ## FAQ


        ### How to handle rate limits?


        When encountering `429 Too Many Requests`, we recommend implementing
        exponential backoff retry:


        ```python

        import time

        import random


        def chat_with_retry(messages, max_retries=3):
            for i in range(max_retries):
                try:
                    response = client.chat.completions.create(
                        model="gpt-4",
                        messages=messages
                    )
                    return response
                except RateLimitError:
                    if i < max_retries - 1:
                        wait_time = (2 ** i) + random.random()
                        time.sleep(wait_time)
                    else:
                        raise
        ```


        ### How to maintain conversation context?


        Include the complete conversation history in the `messages` array:


        ```python

        conversation_history = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a programming language..."},
            {"role": "user", "content": "What are its advantages?"}
        ]

        ```


        ### What does finish_reason mean?


        | Value            | Meaning                    |

        | ---------------- | -------------------------- |

        | `stop`           | Natural completion         |

        | `length`         | Reached max_tokens limit   |

        | `content_filter` | Triggered content filter   |

        | `function_call`  | Model called a function    |


        ### How to control costs?


        1. Use `max_tokens` to limit output length

        2. Choose appropriate models (e.g., gpt-5-mini is more economical)

        3. Streamline prompts, avoid redundant context

        4. Monitor token consumption in the `usage` field
      tags:
        - 💬 Text Models
      parameters:
        - name: Authorization
          in: header
          description: ''
          required: true
          example: Bearer {{api-key}}
          schema:
            type: string
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                model:
                  type: string
                  description: >-
                    ID of the model to be used.For more information on which
                    models are available for the Chat API, see the Model
                    Endpoint Compatibility
                    Table:https://platform.openai.com/docs/models
                messages:
                  type: array
                  items:
                    type: object
                    properties:
                      role:
                        type: string
                        description: role
                      content:
                        type: string
                    x-apidog-orders:
                      - role
                      - content
                  description: >-
                    In Chat
                    Format:https://platform.openai.com/docs/guides/text?api-mode=chat
                    Generate a chat completion message.
                stream:
                  type: boolean
                  description: >-
                    If set, a partial message increment will be sent, as in
                    ChatGPT. When the token is available, the token will be sent
                    as a data-only server send event data: [DONE] and the stream
                    is terminated by the message. For sample code, see the
                    OpenAI Cookbook.
                temperature:
                  type: integer
                  description: >-
                    What sampling temperature to use, between 0 and 1. Higher
                    values (e.g., 0.8) will make the output more random, while
                    lower values (e.g., 0.2) will make the output more
                    concentrated and deterministic. We generally recommend
                    changing this or top_p but not both.
                     gpt-5-chat-latest: Supports custom temperature parameters with a range of 0-1 (including 0 and 1), allowing flexible adjustment as needed.  
                    Other GPT-5 series models: The temperature parameter is
                    fixed at 1; you can set it directly to 1 or choose not to
                    pass it (the system will default to 1).


                    Translated with DeepL.com (free version)
                top_p:
                  type: integer
                  description: >-
                    An alternative to temperature sampling, called kernel
                    sampling, where the model considers the results of markers
                    with top_p probability mass. So 0.1 means that only the
                    markers that make up the top 10% probability mass are
                    considered. We usually recommend changing either this or
                    TEMPERATURE but not both.
                'n':
                  type: integer
                  description: >-
                    How many chat completion options to generate for each input
                    message.
                stop:
                  type: string
                  description: >
                    The API will stop generating more tokens for up to 4
                    sequences.
                max_tokens:
                  type: integer
                  description: >-
                    Maximum number of tokens generated for chat completion. The
                    total length of input tokens and generated tokens is limited
                    by the length of the model context.-When calling the GPT-5
                    series models (excluding gpt-5-chat-latest), the
                    **max_tokens** field should be changed to
                    **max_completion_tokens**.
                presence_penalty:
                  type: number
                  description: >-
                    A number between -2.0 and 2.0. Positive values penalize new
                    tokens based on whether or not they have appeared in the
                    text so far, thus increasing the likelihood that the model
                    will talk about new topics. See more about frequency and
                    presence
                    penalties:https://platform.openai.com/docs/api-reference/parameter-details
                frequency_penalty:
                  type: number
                  description: >-
                    A number between -2.0 and 2.0. Positive values penalize new
                    tokens based on whether or not they have appeared in the
                    text so far, thus increasing the likelihood that the model
                    will talk about new topics. See more about frequency and
                    presence
                    penalties:https://platform.openai.com/docs/api-reference/parameter-details
                logit_bias:
                  type: 'null'
                  description: >-
                    Modifies the likelihood that the specified token will appear
                    in the completion. Accepts a json object that maps markers
                    (specified by the marker ID in the tagger) to an associated
                    deviation value from -100 to 100. Mathematically, the
                    deviations are added to the logits generated by the model
                    before sampling. The exact effect varies from model to
                    model, but values between -1 and 1 should reduce or increase
                    the likelihood of selection; values like -100 or 100 should
                    result in prohibited or exclusive selection of the
                    associated token.
                user:
                  type: string
                  description: >-
                    Unique identifiers that represent your end users can help
                    OpenAI monitor and detect abuse. Learn
                    more:https://platform.openai.com/docs/guides/safety-best-practices/end-user-ids
              x-apidog-orders:
                - model
                - messages
                - stream
                - temperature
                - top_p
                - 'n'
                - stop
                - max_tokens
                - presence_penalty
                - frequency_penalty
                - logit_bias
                - user
              x-apidog-refs: {}
              required:
                - model
                - messages
            examples:
              '1':
                value:
                  model: gpt-5.2
                  messages:
                    - role: system
                      content: You are a helpful assistant.
                    - role: user
                      content: Hello!
                summary: Default
              '2':
                value:
                  model: gpt-4.1
                  messages:
                    - role: user
                      content:
                        - type: text
                          text: What is in this image?
                        - type: image_url
                          image_url:
                            url: https://picsum.photos/1920/1080
                  max_tokens: 300
                summary: Image Input
              '3':
                value:
                  model: gpt-5
                  messages:
                    - role: developer
                      content: You are a helpful assistant.
                    - role: user
                      content: Hello!
                  stream: true
                summary: Streaming
              '4':
                value:
                  model: gpt-4.1
                  messages:
                    - role: user
                      content: What is the weather like in Boston today?
                  tools:
                    - type: function
                      function:
                        name: get_current_weather
                        description: Get the current weather in a given location
                        parameters:
                          type: object
                          properties:
                            location:
                              type: string
                              description: The city and state, e.g. San Francisco, CA
                            unit:
                              type: string
                              enum:
                                - celsius
                                - fahrenheit
                          required:
                            - location
                  tool_choice: auto
                summary: Functions
              '5':
                value:
                  model: gpt-5
                  messages:
                    - role: user
                      content: Hello!
                  logprobs: true
                  top_logprobs: 2
                summary: Logprobs
      responses:
        '200':
          description: ''
          content:
            application/json:
              schema:
                type: object
                properties:
                  model:
                    type: string
                    description: >-
                      ID of the model to use. See the model endpoint
                      compatibility table for details on which models work with
                      the Chat API:
                      https://platform.openai.com/docs/models/model-endpoint-compatibility
                  messages:
                    type: array
                    items:
                      type: object
                      properties:
                        role:
                          type: string
                          description: The role of the message sender
                        content:
                          type: string
                          description: The content of the message
                      x-apifox-orders:
                        - role
                        - content
                      x-apidog-orders:
                        - role
                        - content
                    description: >
                      A list of messages comprising the conversation so far. See
                      the chat format guide:
                      https://platform.openai.com/docs/guides/text?api-mode=chat
                  stream:
                    type: boolean
                    description: >
                      If set, partial message deltas will be sent, like in
                      ChatGPT. Tokens will be sent as data-only server-sent
                      events as they become available, with the stream
                      terminated by a data: [DONE] message. See the OpenAI
                      Cookbook for example code.
                  temperature:
                    type: integer
                    description: >-
                      What sampling temperature to use, between 0 and 1. Higher
                      values like 0.8 will make the output more random, while
                      lower values like 0.2 will make it more focused and
                      deterministic. We generally recommend altering this or
                      top_p but not both.
                       gpt-5-chat-latest: Supports custom temperature parameter, value range 0-1 (including 0 and 1), can be flexibly adjusted as needed.
                       Other GPT-5 series models: Temperature parameter is fixed at 1, you can directly set it to 1 or choose not to pass it (the system will default to 1).
                  top_p:
                    type: integer
                    description: >-
                      An alternative to sampling with temperature, called
                      nucleus sampling, where the model considers the results of
                      the tokens with top_p probability mass. So 0.1 means only
                      the tokens comprising the top 10% probability mass are
                      considered. We generally recommend altering this or
                      temperature but not both.
                  'n':
                    type: integer
                    description: >
                      How many chat completion choices to generate for each
                      input message.
                  stop:
                    type: string
                    description: >
                      Up to 4 sequences where the API will stop generating
                      further tokens.
                  max_tokens:
                    type: integer
                    description: >
                      The maximum number of tokens to generate in the chat
                      completion. The total length of input tokens and generated
                      tokens is limited by the model's context length. When
                      calling GPT-5 series models (except gpt-5-chat-latest),
                      the **max_tokens** field should be changed to
                      **max_completion_tokens**.
                  presence_penalty:
                    type: number
                    description: >-
                      Number between -2.0 and 2.0. Positive values penalize new
                      tokens based on whether they appear in the text so far,
                      increasing the model's likelihood to talk about new
                      topics. See more information about frequency and presence
                      penalties:
                      https://platform.openai.com/docs/api-reference/parameter-details
                  frequency_penalty:
                    type: number
                    description: >-
                      Number between -2.0 and 2.0. Positive values penalize new
                      tokens based on their existing frequency in the text so
                      far, decreasing the model's likelihood to repeat the same
                      line verbatim. See more information about frequency and
                      presence penalties:
                      https://platform.openai.com/docs/api-reference/parameter-details
                  logit_bias:
                    type: 'null'
                    description: >
                      Modify the likelihood of specified tokens appearing in the
                      completion. Accepts a json object that maps tokens
                      (specified by their token ID in the tokenizer) to an
                      associated bias value from -100 to 100. Mathematically,
                      the bias is added to the logits generated by the model
                      prior to sampling. The exact effect will vary per model,
                      but values between -1 and 1 should decrease or increase
                      likelihood of selection; values like -100 or 100 should
                      result in a ban or exclusive selection of the relevant
                      token.
                  user:
                    type: string
                    description: >-
                      A unique identifier representing your end-user, which can
                      help OpenAI to monitor and detect abuse. Learn more:
                      https://platform.openai.com/docs/guides/safety-best-practices/end-user-ids
                required:
                  - model
                  - messages
                x-apidog-orders:
                  - model
                  - messages
                  - stream
                  - temperature
                  - top_p
                  - 'n'
                  - stop
                  - max_tokens
                  - presence_penalty
                  - frequency_penalty
                  - logit_bias
                  - user
              examples:
                '1':
                  summary: Default
                  value:
                    id: chatcmpl-CbnYmQAVmFC6IzQTs9X0bFc3J1S7q
                    object: chat.completion
                    created: 1763124680
                    model: gpt-5.1-2025-11-13
                    choices:
                      - index: 0
                        message:
                          role: assistant
                          content: Hello! How can I help you today?
                          refusal: null
                          annotations: []
                        finish_reason: stop
                    usage:
                      prompt_tokens: 18
                      completion_tokens: 18
                      total_tokens: 36
                      prompt_tokens_details:
                        cached_tokens: 0
                        audio_tokens: 0
                      completion_tokens_details:
                        reasoning_tokens: 0
                        audio_tokens: 0
                        accepted_prediction_tokens: 0
                        rejected_prediction_tokens: 0
                    service_tier: default
                    system_fingerprint: null
                '2':
                  summary: Image Input
                  value:
                    id: chatcmpl-CaYdcgTrUITTSGco8dTSSauJMMDTt
                    object: chat.completion
                    created: 1762828992
                    model: gpt-4.1-2025-04-14
                    choices:
                      - index: 0
                        message:
                          role: assistant
                          content: >-
                            This image shows a calm, misty lakeshore or seashore
                            scene. In the foreground, there are many large rocks
                            and boulders. A single weathered wooden post stands
                            upright among the rocks. The water is smooth and
                            peaceful, fading into the distance with a soft, hazy
                            sky above. The colors are muted, mostly brown, gray,
                            and soft yellow tones, giving a tranquil and serene
                            atmosphere.
                          refusal: null
                          annotations: []
                        logprobs: null
                        finish_reason: stop
                    usage:
                      prompt_tokens: 921
                      completion_tokens: 85
                      total_tokens: 1006
                      prompt_tokens_details:
                        cached_tokens: 0
                        audio_tokens: 0
                      completion_tokens_details:
                        reasoning_tokens: 0
                        audio_tokens: 0
                        accepted_prediction_tokens: 0
                        rejected_prediction_tokens: 0
                    system_fingerprint: fp_f99638a8d7
                '3':
                  summary: Functions
                  value:
                    id: chatcmpl-CaYfDl9drSufstEpDX4sRyvjxX3z1
                    object: chat.completion
                    created: 1762829091
                    model: gpt-4.1-2025-04-14
                    choices:
                      - index: 0
                        message:
                          role: assistant
                          content: null
                          tool_calls:
                            - id: call_K0ODWHqaHnU7OOBYEFaMznnI
                              type: function
                              function:
                                name: get_current_weather
                                arguments: '{"location":"Boston, MA"}'
                          refusal: null
                          annotations: []
                        logprobs: null
                        finish_reason: tool_calls
                    usage:
                      prompt_tokens: 81
                      completion_tokens: 18
                      total_tokens: 99
                      prompt_tokens_details:
                        cached_tokens: 0
                        audio_tokens: 0
                      completion_tokens_details:
                        reasoning_tokens: 0
                        audio_tokens: 0
                        accepted_prediction_tokens: 0
                        rejected_prediction_tokens: 0
                    system_fingerprint: fp_f99638a8d7
                '4':
                  summary: Logprobs
                  value:
                    id: chatcmpl-CaYfhVysuGFdrNBmHWy4JS6iTOW9w
                    object: chat.completion
                    created: 1762829116
                    model: gpt-5
                    choices:
                      - index: 0
                        message:
                          role: assistant
                          content: Hello, how may I assist you?
                          refusal: null
                          annotations: []
                        logprobs: null
                        finish_reason: stop
                    usage:
                      prompt_tokens: 11
                      completion_tokens: 11
                      total_tokens: 22
                      prompt_tokens_details:
                        cached_tokens: 0
                        audio_tokens: 0
                      completion_tokens_details:
                        reasoning_tokens: 0
                        audio_tokens: 0
                        accepted_prediction_tokens: 0
                        rejected_prediction_tokens: 0
                    service_tier: default
                    system_fingerprint: fp_0824345751
          headers: {}
          x-apidog-name: Image Input
      security: []
      x-apidog-folder: 💬 Text Models
      x-apidog-status: released
      x-run-in-apidog: https://app.apidog.com/web/project/810968/apis/api-13851472-run
components:
  schemas: {}
  securitySchemes: {}
servers:
  - url: https://api.cometapi.com
    description: Prod Env
security: []

```