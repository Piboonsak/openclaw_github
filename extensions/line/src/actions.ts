import type { messagingApi } from "@line/bot-sdk";

export type Action = messagingApi.Action;

export function messageAction(label: string, text?: string): Action {
  return {
    type: "message",
    label: label.slice(0, 20),
    text: text ?? label,
  };
}

export function uriAction(label: string, uri: string): Action {
  return {
    type: "uri",
    label: label.slice(0, 20),
    uri,
  };
}

export function postbackAction(label: string, data: string, displayText?: string): Action {
  return {
    type: "postback",
    label: label.slice(0, 20),
    data,
    displayText: displayText?.slice(0, 300),
  };
}

export function datetimePickerAction(
  label: string,
  data: string,
  mode: "date" | "time" | "datetime" = "datetime",
  initial?: string,
  min?: string,
  max?: string,
): Action {
  return {
    type: "datetimepicker",
    label: label.slice(0, 20),
    data,
    mode,
    initial,
    min,
    max,
  };
}
