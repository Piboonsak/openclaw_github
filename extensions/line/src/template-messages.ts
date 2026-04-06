import type { messagingApi } from "@line/bot-sdk";
import {
  datetimePickerAction,
  messageAction,
  postbackAction,
  uriAction,
  type Action,
} from "./actions.js";
import type { LineTemplateMessagePayload } from "./types.js";

export { datetimePickerAction, messageAction, postbackAction, uriAction };

type TemplateMessage = messagingApi.TemplateMessage;
type ConfirmTemplate = messagingApi.ConfirmTemplate;
type ButtonsTemplate = messagingApi.ButtonsTemplate;
type CarouselTemplate = messagingApi.CarouselTemplate;
type CarouselColumn = messagingApi.CarouselColumn;
type ImageCarouselTemplate = messagingApi.ImageCarouselTemplate;
type ImageCarouselColumn = messagingApi.ImageCarouselColumn;

export function createConfirmTemplate(
  text: string,
  confirmAction: Action,
  cancelAction: Action,
  altText?: string,
): TemplateMessage {
  const template: ConfirmTemplate = {
    type: "confirm",
    text: text.slice(0, 240),
    actions: [confirmAction, cancelAction],
  };

  return {
    type: "template",
    altText: altText?.slice(0, 400) ?? text.slice(0, 400),
    template,
  };
}

export function createButtonTemplate(
  title: string,
  text: string,
  actions: Action[],
  options?: {
    thumbnailImageUrl?: string;
    imageAspectRatio?: "rectangle" | "square";
    imageSize?: "cover" | "contain";
    imageBackgroundColor?: string;
    defaultAction?: Action;
    altText?: string;
  },
): TemplateMessage {
  const hasThumbnail = Boolean(options?.thumbnailImageUrl?.trim());
  const textLimit = hasThumbnail ? 160 : 60;
  const template: ButtonsTemplate = {
    type: "buttons",
    title: title.slice(0, 40),
    text: text.slice(0, textLimit),
    actions: actions.slice(0, 4),
    thumbnailImageUrl: options?.thumbnailImageUrl,
    imageAspectRatio: options?.imageAspectRatio ?? "rectangle",
    imageSize: options?.imageSize ?? "cover",
    imageBackgroundColor: options?.imageBackgroundColor,
    defaultAction: options?.defaultAction,
  };

  return {
    type: "template",
    altText: options?.altText?.slice(0, 400) ?? `${title}: ${text}`.slice(0, 400),
    template,
  };
}

export function createTemplateCarousel(
  columns: CarouselColumn[],
  options?: {
    imageAspectRatio?: "rectangle" | "square";
    imageSize?: "cover" | "contain";
    altText?: string;
  },
): TemplateMessage {
  const template: CarouselTemplate = {
    type: "carousel",
    columns: columns.slice(0, 10),
    imageAspectRatio: options?.imageAspectRatio ?? "rectangle",
    imageSize: options?.imageSize ?? "cover",
  };

  return {
    type: "template",
    altText: options?.altText?.slice(0, 400) ?? "View carousel",
    template,
  };
}

export function createCarouselColumn(params: {
  title?: string;
  text: string;
  actions: Action[];
  thumbnailImageUrl?: string;
  imageBackgroundColor?: string;
  defaultAction?: Action;
}): CarouselColumn {
  return {
    title: params.title?.slice(0, 40),
    text: params.text.slice(0, 120),
    actions: params.actions.slice(0, 3),
    thumbnailImageUrl: params.thumbnailImageUrl,
    imageBackgroundColor: params.imageBackgroundColor,
    defaultAction: params.defaultAction,
  };
}

export function createImageCarousel(
  columns: ImageCarouselColumn[],
  altText?: string,
): TemplateMessage {
  const template: ImageCarouselTemplate = {
    type: "image_carousel",
    columns: columns.slice(0, 10),
  };

  return {
    type: "template",
    altText: altText?.slice(0, 400) ?? "View images",
    template,
  };
}

export function buildTemplateMessageFromPayload(
  payload: LineTemplateMessagePayload,
): TemplateMessage | null {
  switch (payload.type) {
    case "confirm": {
      const confirmAction = payload.confirmData.startsWith("http")
        ? uriAction(payload.confirmLabel, payload.confirmData)
        : payload.confirmData.includes("=")
          ? postbackAction(payload.confirmLabel, payload.confirmData, payload.confirmLabel)
          : messageAction(payload.confirmLabel, payload.confirmData);

      const cancelAction = payload.cancelData.startsWith("http")
        ? uriAction(payload.cancelLabel, payload.cancelData)
        : payload.cancelData.includes("=")
          ? postbackAction(payload.cancelLabel, payload.cancelData, payload.cancelLabel)
          : messageAction(payload.cancelLabel, payload.cancelData);

      return createConfirmTemplate(payload.text, confirmAction, cancelAction, payload.altText);
    }

    case "buttons": {
      const actions: Action[] = payload.actions.slice(0, 4).map((action) => {
        if (action.type === "uri" && action.uri) {
          return uriAction(action.label, action.uri);
        }
        if (action.type === "postback" && action.data) {
          return postbackAction(action.label, action.data, action.label);
        }
        return messageAction(action.label, action.data ?? action.label);
      });

      return createButtonTemplate(payload.title, payload.text, actions, {
        thumbnailImageUrl: payload.thumbnailImageUrl,
        altText: payload.altText,
      });
    }

    case "carousel": {
      const columns: CarouselColumn[] = payload.columns.slice(0, 10).map((col) => {
        const colActions: Action[] = col.actions.slice(0, 3).map((action) => {
          if (action.type === "uri" && action.uri) {
            return uriAction(action.label, action.uri);
          }
          if (action.type === "postback" && action.data) {
            return postbackAction(action.label, action.data, action.label);
          }
          return messageAction(action.label, action.data ?? action.label);
        });

        return createCarouselColumn({
          title: col.title,
          text: col.text,
          thumbnailImageUrl: col.thumbnailImageUrl,
          actions: colActions,
        });
      });

      return createTemplateCarousel(columns, { altText: payload.altText });
    }

    default:
      return null;
  }
}

export type {
  TemplateMessage,
  ConfirmTemplate,
  ButtonsTemplate,
  CarouselTemplate,
  CarouselColumn,
  ImageCarouselTemplate,
  ImageCarouselColumn,
  Action,
};
