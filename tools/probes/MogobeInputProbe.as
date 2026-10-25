package {
    import flash.display.MovieClip;
    import flash.display.Loader;
    import flash.events.Event;
    import flash.events.IOErrorEvent;
    import flash.external.ExternalInterface;
    import flash.net.URLRequest;
    import flash.system.LoaderContext;
    import flash.system.ApplicationDomain;
    import flash.text.TextField;
    import flash.text.TextFieldAutoSize;
    import flash.text.TextFormat;
    import flash.text.TextFormatAlign;
    import flash.geom.Rectangle;
    import flash.utils.Dictionary;

    public dynamic class MogobeInputProbe extends MovieClip {
        private var fontsLoader:Loader;
        private var fields:Object = {};
        private var ready:Boolean = false;
        private var error:String = "";
        public function MogobeInputProbe() {
            ExternalInterface.addCallback("snapshot",snapshot);
            fontsLoader = new Loader();
            fontsLoader.contentLoaderInfo.addEventListener(Event.COMPLETE,loaded);
            fontsLoader.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR,function(e:IOErrorEvent):void {error=e.text;});
            fontsLoader.load(new URLRequest("/Swf/Login.swf"),new LoaderContext(false,ApplicationDomain.currentDomain));
            if (loaderInfo.parameters.applyFix == "true") {
                addEventListener(Event.EXIT_FRAME,function(event:Event):void {updateFocusedInput();});
                addEventListener(Event.RENDER,function(event:Event):void {updateFocusedInput();});
            }
        }
        private function loaded(event:Event):void {
            var cls:Class = ApplicationDomain.currentDomain.getDefinition("FontClass") as Class;
            Object(cls).getInstance();
            addInput("deviceLeft",35,false,"left",false,false);
            addInput("deviceRight",85,false,"right",false,false);
            addInput("embeddedLeft",135,true,"left",false,false);
            addInput("embeddedRight",185,true,"right",false,false);
            addInput("password",235,true,"left",true,false);
            addInput("multiline",285,true,"left",false,true);
            ready = true;
        }
        private function addInput(name:String,y:Number,embedded:Boolean,align:String,password:Boolean,multiline:Boolean):void {
            var label:TextField = new TextField();
            label.defaultTextFormat = new TextFormat("Arial",15,0x222222);
            label.text = name;
            label.x = 15;label.y = y+7;label.width=195;label.height=24;
            label.mouseEnabled=false;addChild(label);
            var field:TextField = new TextField();
            field.name=name;field.type="input";
            field.x=220;field.y=y;field.width=300;field.height=multiline ? 140 : 34;
            field.defaultTextFormat=new TextFormat("Arial",18,0x111111,false,false,false,null,null,align);
            field.embedFonts=embedded;field.displayAsPassword=password;
            field.multiline=multiline;field.wordWrap=multiline;field.maxChars=1200;
            field.border=true;field.background=true;field.backgroundColor=0xffffff;
            addChild(field);fields[name]=field;
        }
        public function snapshot():Object {
            var rows:Array=[];
            for (var name:String in fields) {
                var f:TextField=fields[name];
                var bounds:Rectangle=f.getBounds(this);
                var caret:Rectangle=f.caretIndex>0 ? f.getCharBoundaries(f.caretIndex-1) : null;
                var first:Rectangle=f.length>0 ? f.getCharBoundaries(0) : null;
                var x:Number=caret==null ? 2 : caret.right;
                var line:int=f.length==0 ? 0 : f.getLineIndexOfChar(Math.min(f.caretIndex,f.length-1));
                rows.push({name:name,length:f.length,caret:f.caretIndex,scrollH:f.scrollH,maxScrollH:f.maxScrollH,
                    caretX:x,caretGap:f.getBounds(f).width-x+f.scrollH,firstX:first==null ? 2 : first.x,
                    align:f.defaultTextFormat.align,scrollV:f.scrollV,bottomScrollV:f.bottomScrollV,
                    caretLine:line+1,textWidth:f.textWidth,width:bounds.width,height:bounds.height,x:bounds.x,y:bounds.y});
            }
            return {ready:ready,error:error,fields:rows};
        }
        /* SHARED_INPUT_COMPATIBILITY */
    }
}
